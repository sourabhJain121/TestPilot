from tree_sitter import Language, Parser
import tree_sitter_python as tspython
from typing import List, Dict, Any

PY_LANGUAGE = Language(tspython.language())

class ASTSymbolExtractor:
    """Parses Python source code into symbol signatures and blocks."""

    def __init__(self):
        self.parser = Parser(PY_LANGUAGE)

    def extract_functions(self, source_code: str) -> List[Dict[str, Any]]:
        source_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        functions = []

        query = PY_LANGUAGE.query("""
            (function_definition
                name: (identifier) @name
                parameters: (parameters) @params
                body: (block) @body) @func
        """)

        captures = query.captures(tree.root_node)
        for node, tag in captures:
            if tag == "func":
                name_node = node.child_by_field_name("name")
                fn_name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8") if name_node else "anonymous"
                raw_code = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
                functions.append({
                    "name": fn_name,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "code": raw_code
                })
        return functions
