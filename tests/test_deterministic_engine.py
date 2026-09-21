"""
Unit tests for OpenAPIBoundaryExtractor and DeterministicBoundaryEngine.
"""

import ast

from typer.testing import CliRunner

from testpilot.cli import app
from testpilot.rag.deterministic_engine import (
    BoundaryCase,
    ConstraintKind,
    DeterministicBoundaryEngine,
    OpenAPIBoundaryExtractor,
)

runner = CliRunner()


def test_extractor_initialization_and_schema_discovery():
    extractor = OpenAPIBoundaryExtractor("testbed/openapi.json")
    assert "CartItem" in extractor.schemas
    assert "OrderTotals" in extractor.schemas
    assert "CouponApplyRequest" in extractor.schemas
    assert "OrderStatus" in extractor.schemas


def test_extractor_numeric_boundary_cases():
    extractor = OpenAPIBoundaryExtractor("testbed/openapi.json")
    boundaries = extractor.extract_all_boundaries()
    assert all(isinstance(b, BoundaryCase) for b in boundaries)

    # Verify unit_price exclusiveMinimum boundary
    price_boundaries = [b for b in boundaries if b.schema_name == "CartItem" and b.field_name == "unit_price"]
    assert len(price_boundaries) >= 3
    kinds = [b.constraint_kind for b in price_boundaries]
    assert ConstraintKind.NUMERIC_EXCLUSIVE_MINIMUM in kinds

    # Verify 0.0 is marked expected_valid=False for exclusiveMinimum
    zero_case = next(b for b in price_boundaries if b.boundary_label == "exclusive_min")
    assert zero_case.expected_valid is False
    assert zero_case.boundary_value == 0.0

    # Verify positive price is marked expected_valid=True
    valid_case = next(b for b in price_boundaries if b.boundary_label == "exclusive_min + delta")
    assert valid_case.expected_valid is True
    assert valid_case.boundary_value > 0.0


def test_extractor_string_and_enum_boundaries():
    extractor = OpenAPIBoundaryExtractor("testbed/openapi.json")
    boundaries = extractor.extract_all_boundaries()

    # String minLength for CartItem name
    name_boundaries = [b for b in boundaries if b.schema_name == "CartItem" and b.field_name == "name"]
    empty_str_case = next(b for b in name_boundaries if b.boundary_label == "empty_string")
    assert empty_str_case.expected_valid is False
    assert empty_str_case.boundary_value == ""

    # Enum boundaries for OrderStatus
    status_boundaries = [b for b in boundaries if b.schema_name == "OrderStatus"]
    assert any(b.boundary_value == "PENDING" and b.expected_valid is True for b in status_boundaries)
    assert any(b.boundary_label == "enum_invalid" and b.expected_valid is False for b in status_boundaries)


def test_synthesize_pytest_suite_generates_valid_ast(tmp_path):
    output_test_file = tmp_path / "test_generated_boundaries.py"
    code = DeterministicBoundaryEngine.synthesize_pytest_suite(
        spec_path="testbed/openapi.json",
        output_path=output_test_file,
    )

    assert output_test_file.exists()
    assert len(code) > 500
    # Must parse cleanly with Python AST parser without SyntaxError
    parsed = ast.parse(code)
    assert isinstance(parsed, ast.Module)
    assert "def test_cart_item_unit_price" in code
    assert "def test_order_totals_minimum" in code


def test_cli_generate_deterministic_command(tmp_path):
    output_path = tmp_path / "test_cli_boundaries.py"
    res = runner.invoke(
        app,
        ["generate-deterministic", "--spec", "testbed/openapi.json", "--output", str(output_path)],
    )

    assert res.exit_code == 0
    assert "Successfully synthesized deterministic test suite" in res.stdout
    assert output_path.exists()
    assert output_path.stat().st_size > 0
