from src/testpilot.code_intel.treesitter_parser import ASTSymbolExtractor

def test_ast_function_extraction():
    sample_code = """
def sample_add(a: int, b: int) -> int:
    return a + b
"""
    extractor = ASTSymbolExtractor()
    extracted = extractor.extract_functions(sample_code)
    assert len(extracted) == 1
    assert extracted[0]["name"] == "sample_add"
    assert "return a + b" in extracted[0]["code"]
