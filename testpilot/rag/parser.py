"""
Semantic OpenAPI and Markdown Document Chunker for TestPilot AI.
Extracts structured specification chunks from OpenAPI 3.1 endpoints,
schema models, and Markdown PRDs with rich metadata for vector indexing.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SpecChunk(BaseModel):
    """Represents a discrete semantic chunk of technical specifications."""

    id: str = Field(..., description="Deterministic hash ID for deduplication")
    content: str = Field(..., description="Text content formatted for embedding & LLM retrieval")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Categorization metadata")


class SpecParser:
    """Parses OpenAPI 3.1 definitions and Markdown documentation into semantic chunks."""

    @classmethod
    def _generate_chunk_id(cls, content: str, prefix: str) -> str:
        h = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()[:16]
        return f"{prefix}_{h}"

    @classmethod
    def parse_openapi(cls, openapi_path: str) -> list[SpecChunk]:
        """
        Parses an OpenAPI 3.1 JSON or YAML specification into:
        1. Endpoint chunks: paths/{path}/{method}
        2. Schema chunks: components/schemas/{ModelName}
        """
        path = Path(openapi_path)
        if not path.exists():
            raise FileNotFoundError(f"OpenAPI file not found at: {openapi_path}")

        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)

        chunks: list[SpecChunk] = []

        # 1. Parse Paths & Operations
        paths = data.get("paths", {})
        for route_path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue

                summary = operation.get("summary", "No summary")
                description = operation.get("description", "No description")
                tags = ", ".join(operation.get("tags", [])) or "None"

                # Request Body
                req_body = operation.get("requestBody", {})
                req_content = req_body.get("content", {})
                req_schema_repr = "None"
                for media_type, media_info in req_content.items():
                    schema = media_info.get("schema", {})
                    ref = schema.get("$ref") or (
                        schema.get("items", {}).get("$ref") if schema.get("type") == "array" else None
                    )
                    req_schema_repr = f"Media: {media_type}, Schema Ref: {ref or schema}"

                # Responses
                responses = operation.get("responses", {})
                resp_lines = []
                for status_code, resp_info in responses.items():
                    resp_desc = resp_info.get("description", "")
                    resp_lines.append(f"  - Status {status_code}: {resp_desc}")
                resp_repr = "\n".join(resp_lines) or "  - None specified"

                # Parameters
                params = operation.get("parameters", [])
                param_lines = [
                    f"  - {p.get('name')} in {p.get('in')} (required={p.get('required', False)}): {p.get('description', '')}"
                    for p in params
                ]
                param_repr = "\n".join(param_lines) or "  - None"

                chunk_text = (
                    f"OPENAPI SPECIFICATION ENDPOINT:\n"
                    f"Route: {method.upper()} {route_path}\n"
                    f"Tags: {tags}\n"
                    f"Summary: {summary}\n"
                    f"Description: {description}\n"
                    f"Parameters:\n{param_repr}\n"
                    f"Request Body: {req_schema_repr}\n"
                    f"Responses:\n{resp_repr}"
                )

                chunk_id = cls._generate_chunk_id(chunk_text, prefix=f"ep_{method.lower()}")
                chunks.append(
                    SpecChunk(
                        id=chunk_id,
                        content=chunk_text,
                        metadata={
                            "source": "openapi",
                            "type": "endpoint",
                            "symbol": f"{method.upper()} {route_path}",
                            "path": route_path,
                            "endpoint": route_path,
                            "method": method.upper(),
                        },
                    )
                )

        # 2. Parse Component Schemas
        schemas = data.get("components", {}).get("schemas", {})
        for model_name, schema_info in schemas.items():
            model_type = schema_info.get("type", "object")
            description = schema_info.get("description", "No description")
            required_fields = ", ".join(schema_info.get("required", [])) or "None"

            props = schema_info.get("properties", {})
            prop_lines = []
            for prop_name, prop_meta in props.items():
                p_type = prop_meta.get("type", "any")
                p_desc = prop_meta.get("description", "")
                constraints = []
                for constraint in ("gt", "ge", "lt", "le", "min_length", "max_length", "minimum", "maximum"):
                    if constraint in prop_meta:
                        constraints.append(f"{constraint}={prop_meta[constraint]}")
                constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
                prop_lines.append(f"  - {prop_name}: {p_type}{constraint_str} (description: {p_desc})")

            prop_repr = "\n".join(prop_lines) or "  - None"

            chunk_text = (
                f"OPENAPI COMPONENT SCHEMA MODEL:\n"
                f"Model Name: {model_name}\n"
                f"Type: {model_type}\n"
                f"Description: {description}\n"
                f"Required Fields: {required_fields}\n"
                f"Properties and Constraints:\n{prop_repr}"
            )

            chunk_id = cls._generate_chunk_id(chunk_text, prefix=f"schema_{model_name.lower()}")
            chunks.append(
                SpecChunk(
                    id=chunk_id,
                    content=chunk_text,
                    metadata={
                        "source": "openapi",
                        "type": "schema",
                        "symbol": model_name,
                        "model_name": model_name,
                    },
                )
            )

        return chunks

    @classmethod
    def parse_markdown(cls, markdown_path: str) -> list[SpecChunk]:
        """
        Parses a Markdown technical document, splitting semantically by headers (##, ###).
        """
        path = Path(markdown_path)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        raw_text = path.read_text(encoding="utf-8")
        chunks: list[SpecChunk] = []

        # Split by level 2 and 3 headers
        sections = re.split(r"\n(?=#{2,3}\s+)", raw_text)
        file_name = path.name

        for section in sections:
            cleaned = section.strip()
            if not cleaned or len(cleaned) < 25:
                continue

            first_line = cleaned.splitlines()[0]
            header_match = re.match(r"^#{2,3}\s+(.*)", first_line)
            header_title = header_match.group(1).strip() if header_match else "Overview"

            chunk_text = f"SPECIFICATION DOCUMENT SECTION ({file_name} -> {header_title}):\n{cleaned}"
            chunk_id = cls._generate_chunk_id(chunk_text, prefix=f"doc_{file_name[:4]}")

            chunks.append(
                SpecChunk(
                    id=chunk_id,
                    content=chunk_text,
                    metadata={
                        "source": "markdown",
                        "type": "specification",
                        "header": header_title,
                        "file": str(path),
                        "file_name": file_name,
                    },
                )
            )

        return chunks

    @classmethod
    def parse_all(cls, openapi_path: str = "testbed/openapi.json", docs_dir: str = "docs") -> list[SpecChunk]:
        """Extract all chunks from both OpenAPI contracts and Markdown docs."""
        chunks: list[SpecChunk] = []

        if Path(openapi_path).exists():
            chunks.extend(cls.parse_openapi(openapi_path))

        docs_path = Path(docs_dir)
        if docs_path.exists() and docs_path.is_dir():
            for md_file in docs_path.glob("*.md"):
                chunks.extend(cls.parse_markdown(str(md_file)))

        # Also parse README.md if present
        readme = Path("README.md")
        if readme.exists():
            chunks.extend(cls.parse_markdown(str(readme)))

        return chunks
