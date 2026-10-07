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
    Resolves imported symbols, aliases, and receiver modules to prevent false matches.
    """

    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root).resolve()

    @staticmethod
    def _module_matches_path(module_str: str, file_path: Optional[str]) -> bool:
        """Determines if an imported module name could correspond to the given target file path."""
        if not file_path or not module_str:
            return True
        norm_path = file_path.replace("\\", "/").rstrip(".py")
        if norm_path.endswith("/__init__"):
            norm_path = norm_path[:-9]
        path_parts = [p for p in norm_path.split("/") if p and p != "."]
        mod_parts = [m for m in module_str.split(".") if m]
        if not mod_parts or not path_parts:
            return True
        mod_joined = ".".join(mod_parts)
        path_joined = ".".join(path_parts)
        if mod_joined == path_joined:
            return True
        if path_joined.startswith(mod_joined + "."):
            return True
        if mod_joined.startswith(path_joined + "."):
            return True
        if path_joined.endswith("." + mod_joined) or mod_joined.endswith("." + path_joined):
            return True
        return False

    GENERIC_METHOD_NAMES = {
        "__init__", "setUp", "tearDown", "setUpClass", "tearDownClass", "setUpTestData",
        "setup_method", "teardown_method", "setup_class", "teardown_class",
        "run", "close", "status", "execute", "start", "stop", "reset", "clear",
        "get", "set", "update", "delete", "handle", "process", "validate",
        "save", "create", "filter", "all", "exists", "count", "send", "connect",
    }

    def find_callers(
        self,
        target_function_name: str,
        target_file_path: Optional[str] = None,
        target_class_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Scan all Python files in the repo and find functions or methods that call target_function_name.
        Resolves Python imports, aliases, class scopes, and constructors to distinguish confirmed from ambiguous matches.
        """
        callers: list[dict[str, Any]] = []
        norm_target_path = None
        if target_file_path:
            norm_target_path = target_file_path.replace("\\", "/").lstrip("./")

        # Fast pre-filter target terms to check in file source
        search_terms = {target_function_name}
        if target_class_name:
            search_terms.add(target_class_name)

        for py_file in self.repo_root.rglob("*.py"):
            parts = py_file.parts
            if any(p.startswith(".") or p in ("venv", "env", "site-packages", "htmlcov", ".venv") for p in parts):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                # Fast pre-filter: if none of the target terms are in source, skip ast.parse
                if not any(term in source for term in search_terms):
                    continue
                tree = ast.parse(source, filename=str(py_file))
            except Exception:
                continue

            try:
                rel_path = str(py_file.relative_to(self.repo_root)).replace("\\", "/")
            except ValueError:
                rel_path = str(py_file).replace("\\", "/")

            # Step 1: Collect imported symbols and aliases in this file
            # Format: local_symbol_name -> {"source_module": str, "original_symbol": str}
            imported_symbols: dict[str, dict[str, str]] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        as_name = alias.asname or alias.name
                        imported_symbols[as_name] = {
                            "source_module": alias.name,
                            "original_symbol": alias.name.split(".")[-1],
                        }
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module or ""
                    for alias in node.names:
                        as_name = alias.asname or alias.name
                        imported_symbols[as_name] = {
                            "source_module": mod_name,
                            "original_symbol": alias.name,
                        }

            is_same_file = bool(norm_target_path and (rel_path == norm_target_path or rel_path.endswith(norm_target_path)))

            class CallVisitor(ast.NodeVisitor):
                def __init__(self, outer_self, imported_syms, is_same, target_p, rel_p, tgt_cls):
                    self.outer = outer_self
                    self.imported_symbols = imported_syms
                    self.is_same_file = is_same
                    self.norm_target_path = target_p
                    self.rel_path = rel_p
                    self.target_class_name = tgt_cls
                    self.scope_stack: list[str] = []
                    self.class_stack: list[str] = []

                def visit_ClassDef(self, node: ast.ClassDef):
                    self.class_stack.append(node.name)
                    self.generic_visit(node)
                    self.class_stack.pop()

                def visit_FunctionDef(self, node: ast.FunctionDef):
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                    self.scope_stack.append(node.name)
                    self.generic_visit(node)
                    self.scope_stack.pop()

                def visit_Call(self, node: ast.Call):
                    caller_name = self.scope_stack[-1] if self.scope_stack else "<module_level>"
                    matched = False
                    is_ambiguous = False
                    match_quality = "EXACT_AST_CALL"
                    is_constructor_target = (target_function_name == "__init__" and bool(self.target_class_name))

                    if is_constructor_target:
                        # Constructor resolution for target_class_name.__init__
                        if isinstance(node.func, ast.Name):
                            called_id = node.func.id
                            if called_id == self.target_class_name:
                                if called_id in self.imported_symbols:
                                    info = self.imported_symbols[called_id]
                                    if not self.norm_target_path or self.outer._module_matches_path(info["source_module"], self.norm_target_path):
                                        matched = True
                                        match_quality = "CONFIRMED_CONSTRUCTOR_CALL"
                                elif self.is_same_file:
                                    matched = True
                                    match_quality = "SAME_FILE_CONSTRUCTOR_CALL"
                                elif not self.norm_target_path:
                                    matched = True
                                    match_quality = "CONFIRMED_CONSTRUCTOR_CALL"
                        elif isinstance(node.func, ast.Attribute):
                            attr_name = node.func.attr
                            if attr_name == self.target_class_name:
                                full_attr = self._unparse_node(node.func.value)
                                if not self.norm_target_path or self.outer._module_matches_path(full_attr, self.norm_target_path):
                                    matched = True
                                    match_quality = "CONFIRMED_CONSTRUCTOR_CALL"
                            elif attr_name == "__init__":
                                receiver = node.func.value
                                if isinstance(receiver, ast.Name) and receiver.id == self.target_class_name:
                                    matched = True
                                    match_quality = "CONFIRMED_CLASS_METHOD_CALL"
                                elif isinstance(receiver, ast.Name) and receiver.id in ("self", "cls") and self.is_same_file:
                                    if self.class_stack and self.class_stack[-1] == self.target_class_name:
                                        matched = True
                                        match_quality = "SAME_FILE_CLASS_CALL"
                    else:
                        # General function or method call resolution
                        if isinstance(node.func, ast.Name):
                            called_id = node.func.id
                            if called_id in self.imported_symbols:
                                info = self.imported_symbols[called_id]
                                if info["original_symbol"] == target_function_name:
                                    if self.norm_target_path:
                                        if self.outer._module_matches_path(info["source_module"], self.norm_target_path):
                                            matched = True
                                            match_quality = "CONFIRMED_IMPORT_CALL"
                                        else:
                                            matched = False
                                    else:
                                        matched = True
                                        match_quality = "CONFIRMED_IMPORT_CALL"
                            elif called_id == target_function_name:
                                if self.is_same_file:
                                    matched = True
                                    match_quality = "SAME_FILE_AST_CALL"
                                elif target_function_name in LocalCodeGraphFallback.GENERIC_METHOD_NAMES:
                                    # Do not match generic names across files without confirmed import
                                    matched = False
                                elif self.norm_target_path:
                                    matched = True
                                    is_ambiguous = True
                                    match_quality = "AMBIGUOUS_NAME_MATCH"
                                else:
                                    matched = True
                                    match_quality = "EXACT_AST_CALL"

                        elif isinstance(node.func, ast.Attribute):
                            attr_name = node.func.attr
                            if attr_name == target_function_name:
                                receiver = node.func.value
                                if isinstance(receiver, ast.Name):
                                    rec_name = receiver.id
                                    if self.target_class_name and rec_name == self.target_class_name:
                                        matched = True
                                        match_quality = "CONFIRMED_CLASS_METHOD_CALL"
                                    elif self.is_same_file and rec_name in ("self", "cls"):
                                        if not self.target_class_name or (self.class_stack and self.class_stack[-1] == self.target_class_name):
                                            matched = True
                                            match_quality = "SAME_FILE_CLASS_CALL"
                                        else:
                                            matched = False
                                    elif rec_name in self.imported_symbols:
                                        info = self.imported_symbols[rec_name]
                                        if self.norm_target_path:
                                            if self.outer._module_matches_path(info["source_module"], self.norm_target_path):
                                                matched = True
                                                match_quality = "CONFIRMED_CLASS_METHOD_CALL"
                                            else:
                                                matched = False
                                        else:
                                            matched = True
                                            match_quality = "CONFIRMED_CLASS_METHOD_CALL"
                                    else:
                                        if target_function_name in LocalCodeGraphFallback.GENERIC_METHOD_NAMES or self.target_class_name:
                                            matched = False
                                        elif self.norm_target_path:
                                            matched = True
                                            is_ambiguous = True
                                            match_quality = "AMBIGUOUS_ATTRIBUTE_CALL"
                                        else:
                                            matched = True
                                            is_ambiguous = True
                                            match_quality = "AMBIGUOUS_ATTRIBUTE_CALL"
                                elif isinstance(receiver, ast.Attribute):
                                    full_attr = self._unparse_node(receiver)
                                    if self.norm_target_path and self.outer._module_matches_path(full_attr, self.norm_target_path):
                                        matched = True
                                        match_quality = "CONFIRMED_QUALIFIED_CALL"
                                    else:
                                        if target_function_name in LocalCodeGraphFallback.GENERIC_METHOD_NAMES or self.target_class_name:
                                            matched = False
                                        else:
                                            matched = True
                                            is_ambiguous = True
                                            match_quality = "AMBIGUOUS_ATTRIBUTE_CALL"
                                else:
                                    if target_function_name in LocalCodeGraphFallback.GENERIC_METHOD_NAMES or self.target_class_name:
                                        matched = False
                                    else:
                                        matched = True
                                        is_ambiguous = True
                                        match_quality = "AMBIGUOUS_ATTRIBUTE_CALL"

                    if matched:
                        callers.append(
                            {
                                "caller_name": caller_name,
                                "file_path": self.rel_path,
                                "line_number": node.lineno,
                                "source_type": "local_ast_fallback",
                                "is_ambiguous": is_ambiguous,
                                "confidence": "AMBIGUOUS" if is_ambiguous else "CONFIRMED",
                                "match_quality": match_quality,
                            }
                        )

                    self.generic_visit(node)

                @staticmethod
                def _unparse_node(node: ast.AST) -> str:
                    try:
                        return ast.unparse(node)
                    except Exception:
                        return ""

            visitor = CallVisitor(self, imported_symbols, is_same_file, norm_target_path, rel_path, target_class_name)
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

    def is_alive(self) -> bool:
        """
        Check if Sourcegraph host or GraphQL endpoint responds with any HTTP status < 500.
        If the port is open and responding, marks status as ONLINE so terminal table displays green.
        """
        if (
            os.getenv("TESTPILOT_CI_MODE", "").lower() in ("true", "1", "yes")
            or os.getenv("TESTPILOT_OFFLINE_MODE", "").lower() in ("true", "1", "yes")
        ):
            return False

        base_url = self.endpoint.split("/.api/")[0] if "/.api/" in self.endpoint else self.endpoint
        for target in [base_url, self.endpoint]:
            try:
                resp = requests.get(target, timeout=self.timeout)
                if resp.status_code < 500:
                    return True
            except Exception:
                pass

        try:
            resp = requests.post(
                self.endpoint,
                json={"query": "query SiteStatus { site { hasCodeIntelligence } }"},
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            return resp.status_code < 500
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check whether the Sourcegraph OSS instance is responsive and alive."""
        if (
            os.getenv("TESTPILOT_CI_MODE", "").lower() in ("true", "1", "yes")
            or os.getenv("TESTPILOT_OFFLINE_MODE", "").lower() in ("true", "1", "yes")
        ):
            return False
        return self.is_alive()

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

    def get_function_callers(
        self,
        function_name: str,
        file_path: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Find all callers of a function or class method.
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
            if class_name and function_name == "__init__":
                search_str = f"type:references {class_name}"
            elif class_name:
                search_str = f"type:references {class_name}.{function_name}"
            else:
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
        return self.local_fallback.find_callers(function_name, file_path, target_class_name=class_name)
