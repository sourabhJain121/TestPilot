"""
Unit tests for TestPilot AST and unified diff parser.
"""

from testpilot.ast_engine.treesitter_parser import ASTDiffParser


def test_parse_file_extracts_order_service_functions():
    file_path = "testbed/app/services/order_service.py"
    funcs = ASTDiffParser.parse_file(file_path)

    func_names = [f.name for f in funcs]
    assert "calculate_subtotal" in func_names
    assert "calculate_discount" in func_names
    assert "calculate_tax" in func_names
    assert "calculate_order_totals" in func_names
    assert "transition_order_status" in func_names


def test_ast_extracts_parameters_and_types():
    file_path = "testbed/app/services/order_service.py"
    funcs = ASTDiffParser.parse_file(file_path)
    calc_tax = next(f for f in funcs if f.name == "calculate_tax")

    assert len(calc_tax.parameters) == 1
    param = calc_tax.parameters[0]
    assert param.name == "taxable_amount"
    assert param.type_annotation == "float"


def test_ast_boundary_candidates_generated():
    file_path = "testbed/app/services/order_service.py"
    funcs = ASTDiffParser.parse_file(file_path)
    calc_discount = next(f for f in funcs if f.name == "calculate_discount")

    # Should detect boundary candidates for float subtotal and optional coupon_code
    candidate_types = [b.boundary_type for b in calc_discount.boundary_candidates]
    assert "zero" in candidate_types or "negative" in candidate_types
    assert "null_value" in candidate_types or "empty_string" in candidate_types


def test_parse_diff_with_unified_patch():
    diff_text = """--- a/testbed/app/services/order_service.py
+++ b/testbed/app/services/order_service.py
@@ -72,5 +72,7 @@
         taxable_amount = max(0.0, subtotal - discount)
+        # Modified tax computation
+        tax = cls.calculate_tax(taxable_amount)
"""
    analysis = ASTDiffParser.parse_diff(diff_text, repo_root=".")
    assert len(analysis.modified_files) == 1
    assert "testbed/app/services/order_service.py" in analysis.modified_files
    # Function calculate_order_totals spans lines 67-88
    func_names = [f.name for f in analysis.modified_functions]
    assert "calculate_order_totals" in func_names
