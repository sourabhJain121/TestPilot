"""
Tests for Tree-sitter / AST function extraction.
"""

from testpilot.ast_engine.treesitter_parser import ASTDiffParser


def test_ast_symbol_extractor():
    sample_code = """
def sample_add(a: int, b: int) -> int:
    return a + b
"""
    funcs = ASTDiffParser.parse_source(sample_code)
    assert len(funcs) == 1
    assert funcs[0].name == "sample_add"
    assert "return a + b" in funcs[0].raw_source


def test_ast_function_extraction_diff_parser():
    sample_code = """
def sample_add(a: int, b: int) -> int:
    return a + b
"""
    funcs = ASTDiffParser.parse_source(sample_code)
    assert len(funcs) == 1
    assert funcs[0].name == "sample_add"
    assert "return a + b" in funcs[0].raw_source
    assert len(funcs[0].parameters) == 2
    assert funcs[0].parameters[0].name == "a"
    assert funcs[0].parameters[0].type_annotation == "int"
