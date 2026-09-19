"""
Sourcegraph OSS GraphQL Client & Resilient AST Fallback for TestPilot AI.
Interfaces with Sourcegraph server (http://localhost:7080/.api/graphql) to perform
symbol cross-references and discover downstream callers (blast radius).
Includes an autonomous local AST call-graph fallback when Docker is offline.
"""

import ast
import os
from pathlib import Path
from typing import Any, Optional

import requests


class LocalCodeGraphFallback:
    """
    Zero-dependency AST-driven call graph generator that indexes symbol references
    across the repository when Sourcegraph OSS is not running.
    """

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)

    def find_callers(self, target_function_name: str, target_file_path: Optional[str] = None) -> list[dict[str, Any]]:
        """Scan all Python files in the repo and find functions or methods that call target_function_name."""
        callers: list[dict[str, Any]] = []

        for py_file in self.repo_root.rglob("*.py"):
            # Skip hidden, virtual environments and cache
            parts = py_file.parts
            if any(p.startswith(".") or p in ("venv", "env", "site-packages", "htmlcov") for p in parts):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except Exception:
                continue

            class CallVisitor(ast.NodeVisitor):
                def __init__(self, target_name: str, file_rel_path: str):
                    self.target_name = target_name
                    self.file_rel_path = file_rel_path
                    self.scope_stack: list[str] = []

                def visit_FunctionDef(self, node: ast.FunctionDef):
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()

                def visit_Call(self, node: ast.Call):
                    # Check if the call matches target_name
                    called_name = None
                    if isinstance(node.func, ast.Name):
                        called_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        called_name = node.func.attr

                    if called_name == self.target_name:
                        current_caller = self.scope_stack[-1] if self.scope_stack else "<module_level>"
                        callers.append(
                            {
                                "caller_name": current_caller,
                                "file_path": self.file_rel_path,
                                "line_number": node.lineno,
                                "source_type": "local_ast_fallback",
                            }
                        )
                    self.generic_visit(node)

            try:
                rel_path = str(py_file.relative_to(self.repo_root))
            except ValueError:
                rel_path = str(py_file)

            visitor = CallVisitor(target_function_name, rel_path)
            visitor.visit(tree)

        return callers


class SourcegraphClient:
    """
    Client for querying Sourcegraph OSS via GraphQL, with automatic fallback
    to LocalCodeGraphFallback when the server is unreachable.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:7080/.api/graphql",
        access_token: Optional[str] = None,
        timeout: float = 2.0,
        repo_root: str = ".",
    ):
        self.endpoint = os.getenv("SOURCEGRAPH_ENDPOINT", endpoint)
        self.access_token = access_token or os.getenv("SOURCEGRAPH_ACCESS_TOKEN")
        self.timeout = timeout
        self.local_fallback = LocalCodeGraphFallback(repo_root=repo_root)

    def is_available(self) -> bool:
        """Check whether the Sourcegraph OSS instance is responsive."""
        query = """
        query SiteStatus {
            site {
                hasCodeIntelligence
            }
        }
        """
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"token {self.access_token}"

        try:
            resp = requests.post(
                self.endpoint,
                json={"query": query},
                headers=headers,
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def query_symbols(self, symbol_name: str) -> list[dict[str, Any]]:
        """Search for symbol definitions across indexed repositories."""
        if not self.is_available():
            return []

        query = """
        query SearchSymbols($query: String!) {
            search(query: $query, version: V3) {
                results {
                    results {
                        ... on FileMatch {
                            repository {
                                name
                            }
                            file {
                                path
                            }
                            symbols {
                                name
                                kind
                                location {
                                    range {
                                        start { line }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        payload = {
            "query": query,
            "variables": {"query": f"type:symbol {symbol_name}"},
        }
        try:
            resp = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("search", {}).get("results", {}).get("results", [])
        except Exception:
            pass
        return []

    def get_function_callers(self, function_name: str, file_path: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Find all callers of a function.
        Attempts Sourcegraph GraphQL reference search first; falls back to local AST engine.
        """
        if self.is_available():
            # Sourcegraph reference search
            query = """
            query SearchReferences($query: String!) {
                search(query: $query, version: V3) {
                    results {
                        results {
                            ... on FileMatch {
                                file { path }
                                lineMatches {
                                    lineNumber
                                    lineContent
                                }
                            }
                        }
                    }
                }
            }
            """
            search_str = f"type:references {function_name}"
            try:
                resp = requests.post(
                    self.endpoint,
                    json={"query": query, "variables": {"query": search_str}},
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    matches = resp.json().get("data", {}).get("search", {}).get("results", {}).get("results", [])
                    results = []
                    for m in matches:
                        path = m.get("file", {}).get("path")
                        for line in m.get("lineMatches", []):
                            results.append(
                                {
                                    "caller_name": "unknown_sg_caller",
                                    "file_path": path,
                                    "line_number": line.get("lineNumber"),
                                    "line_content": line.get("lineContent"),
                                    "source_type": "sourcegraph_graphql",
                                }
                            )
                    if results:
                        return results
            except Exception:
                pass

        # Resilient Local AST Fallback
        return self.local_fallback.find_callers(function_name, file_path)
