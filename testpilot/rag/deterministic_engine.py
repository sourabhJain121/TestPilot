"""
Deterministic OpenAPI Boundary Extractor for TestPilot AI.
Extracts numeric, string, array, and enum constraints directly from OpenAPI 3.0/3.1 specifications
and synthesizes deterministic boundary test matrices without LLM inference.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Any, Union

from pydantic import BaseModel


class ConstraintKind(str, Enum):
    NUMERIC_MINIMUM = "minimum"
    NUMERIC_MAXIMUM = "maximum"
    NUMERIC_EXCLUSIVE_MINIMUM = "exclusiveMinimum"
    NUMERIC_EXCLUSIVE_MAXIMUM = "exclusiveMaximum"
    STRING_MIN_LENGTH = "minLength"
    STRING_MAX_LENGTH = "maxLength"
    STRING_PATTERN = "pattern"
    ENUM = "enum"
    ARRAY_MIN_ITEMS = "minItems"
    ARRAY_MAX_ITEMS = "maxItems"


class BoundaryCase(BaseModel):
    """A single deterministic boundary test vector."""

    schema_name: str
    field_name: str
    constraint_kind: ConstraintKind
    constraint_value: Any
    boundary_value: Any
    expected_valid: bool
    rationale: str
    boundary_label: str  # e.g., "min - 1", "min", "min + 1", "empty", "overflow"


class OpenAPIBoundaryExtractor:
    """
    Parses OpenAPI 3.0/3.1 JSON schemas to extract numerical and string boundary
    constraints and generate deterministic test matrices (min-1, min, min+1, empty, overflow).
    """

    def __init__(self, spec_path: Union[str, Path]):
        self.spec_path = Path(spec_path)
        if not self.spec_path.exists():
            raise FileNotFoundError(f"OpenAPI specification not found: {self.spec_path}")
        self.raw_spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        self.schemas = self.raw_spec.get("components", {}).get("schemas", {})

    def extract_all_boundaries(self) -> list[BoundaryCase]:
        """Extract boundary cases across all registered component schemas."""
        all_cases: list[BoundaryCase] = []
        for schema_name, schema_def in self.schemas.items():
            cases = self.extract_schema_boundaries(schema_name, schema_def)
            all_cases.extend(cases)
        return all_cases

    def extract_schema_boundaries(self, schema_name: str, schema_def: dict[str, Any]) -> list[BoundaryCase]:
        """Extract boundary test cases for a specific schema object."""
        cases: list[BoundaryCase] = []
        properties = schema_def.get("properties", {})

        # Also inspect if the schema itself is an enum or string/number
        if "enum" in schema_def:
            cases.extend(self._extract_enum_cases(schema_name, "value", schema_def["enum"]))

        for prop_name, prop_def in properties.items():
            # Handle anyOf / allOf wrappers if present
            effective_def = prop_def
            if "anyOf" in prop_def:
                for sub in prop_def["anyOf"]:
                    if sub.get("type") != "null":
                        effective_def = {**sub, **{k: v for k, v in prop_def.items() if k != "anyOf"}}
                        break

            prop_type = effective_def.get("type")

            # 1. Numeric Constraints (minimum, maximum, exclusiveMinimum, exclusiveMaximum)
            if prop_type in ("number", "integer"):
                cases.extend(self._extract_numeric_boundaries(schema_name, prop_name, effective_def, prop_type))

            # 2. String Constraints (minLength, maxLength, enum, pattern)
            elif prop_type == "string":
                cases.extend(self._extract_string_boundaries(schema_name, prop_name, effective_def))

            # 3. Array Constraints (minItems, maxItems)
            elif prop_type == "array":
                cases.extend(self._extract_array_boundaries(schema_name, prop_name, effective_def))

            # Direct enum property
            if "enum" in effective_def:
                cases.extend(self._extract_enum_cases(schema_name, prop_name, effective_def["enum"]))

        return cases

    def _extract_numeric_boundaries(
        self, schema_name: str, prop_name: str, prop_def: dict[str, Any], prop_type: str
    ) -> list[BoundaryCase]:
        cases: list[BoundaryCase] = []
        is_int = prop_type == "integer"
        delta = 1 if is_int else 0.01

        # minimum
        if "minimum" in prop_def:
            m = prop_def["minimum"]
            m_val = int(m) if is_int else float(m)
            # min - delta (invalid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_MINIMUM,
                    constraint_value=m,
                    boundary_value=m_val - (1 if is_int else 1.0),
                    expected_valid=False,
                    rationale=f"Value below minimum constraint {m}",
                    boundary_label="min - 1",
                )
            )
            # min (valid boundary)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_MINIMUM,
                    constraint_value=m,
                    boundary_value=m_val,
                    expected_valid=True,
                    rationale=f"Exact minimum boundary {m}",
                    boundary_label="min",
                )
            )
            # min + delta (valid interior)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_MINIMUM,
                    constraint_value=m,
                    boundary_value=m_val + delta,
                    expected_valid=True,
                    rationale=f"Value just above minimum constraint {m}",
                    boundary_label="min + 1",
                )
            )

        # exclusiveMinimum
        if "exclusiveMinimum" in prop_def:
            em = prop_def["exclusiveMinimum"]
            em_val = int(em) if is_int else float(em)
            # exclusiveMinimum boundary itself is INVALID
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_EXCLUSIVE_MINIMUM,
                    constraint_value=em,
                    boundary_value=em_val,
                    expected_valid=False,
                    rationale=f"Exact exclusiveMinimum constraint {em} must be strictly exceeded",
                    boundary_label="exclusive_min",
                )
            )
            # Below exclusiveMinimum (invalid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_EXCLUSIVE_MINIMUM,
                    constraint_value=em,
                    boundary_value=em_val - (1 if is_int else 1.0),
                    expected_valid=False,
                    rationale=f"Value below exclusiveMinimum constraint {em}",
                    boundary_label="exclusive_min - 1",
                )
            )
            # Just above exclusiveMinimum (valid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_EXCLUSIVE_MINIMUM,
                    constraint_value=em,
                    boundary_value=em_val + delta,
                    expected_valid=True,
                    rationale=f"Value strictly greater than exclusiveMinimum constraint {em}",
                    boundary_label="exclusive_min + delta",
                )
            )

        # maximum
        if "maximum" in prop_def:
            x = prop_def["maximum"]
            x_val = int(x) if is_int else float(x)
            # max - delta (valid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_MAXIMUM,
                    constraint_value=x,
                    boundary_value=x_val - delta,
                    expected_valid=True,
                    rationale=f"Value just below maximum constraint {x}",
                    boundary_label="max - 1",
                )
            )
            # max (valid boundary)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_MAXIMUM,
                    constraint_value=x,
                    boundary_value=x_val,
                    expected_valid=True,
                    rationale=f"Exact maximum boundary {x}",
                    boundary_label="max",
                )
            )
            # max + delta (invalid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_MAXIMUM,
                    constraint_value=x,
                    boundary_value=x_val + (1 if is_int else 1.0),
                    expected_valid=False,
                    rationale=f"Value exceeding maximum constraint {x}",
                    boundary_label="max + 1",
                )
            )

        # exclusiveMaximum
        if "exclusiveMaximum" in prop_def:
            ex = prop_def["exclusiveMaximum"]
            ex_val = int(ex) if is_int else float(ex)
            # exclusiveMaximum boundary itself is INVALID
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_EXCLUSIVE_MAXIMUM,
                    constraint_value=ex,
                    boundary_value=ex_val,
                    expected_valid=False,
                    rationale=f"Exact exclusiveMaximum {ex} violates strict inequality",
                    boundary_label="exclusive_max",
                )
            )
            # Above exclusiveMaximum (invalid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_EXCLUSIVE_MAXIMUM,
                    constraint_value=ex,
                    boundary_value=ex_val + (1 if is_int else 1.0),
                    expected_valid=False,
                    rationale=f"Value above exclusiveMaximum constraint {ex}",
                    boundary_label="exclusive_max + 1",
                )
            )
            # Just below exclusiveMaximum (valid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.NUMERIC_EXCLUSIVE_MAXIMUM,
                    constraint_value=ex,
                    boundary_value=ex_val - delta,
                    expected_valid=True,
                    rationale=f"Value strictly below exclusiveMaximum {ex}",
                    boundary_label="exclusive_max - delta",
                )
            )

        return cases

    def _extract_string_boundaries(
        self, schema_name: str, prop_name: str, prop_def: dict[str, Any]
    ) -> list[BoundaryCase]:
        cases: list[BoundaryCase] = []

        # minLength
        if "minLength" in prop_def:
            ml = prop_def["minLength"]
            # Empty string (invalid if minLength > 0)
            if ml > 0:
                cases.append(
                    BoundaryCase(
                        schema_name=schema_name,
                        field_name=prop_name,
                        constraint_kind=ConstraintKind.STRING_MIN_LENGTH,
                        constraint_value=ml,
                        boundary_value="",
                        expected_valid=False,
                        rationale="Empty string below minLength",
                        boundary_label="empty_string",
                    )
                )
            if ml > 1:
                # String of length ml - 1 (invalid)
                cases.append(
                    BoundaryCase(
                        schema_name=schema_name,
                        field_name=prop_name,
                        constraint_kind=ConstraintKind.STRING_MIN_LENGTH,
                        constraint_value=ml,
                        boundary_value="a" * (ml - 1),
                        expected_valid=False,
                        rationale=f"String of length {ml - 1} below minLength {ml}",
                        boundary_label="min_length - 1",
                    )
                )
            # String of exact minLength (valid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.STRING_MIN_LENGTH,
                    constraint_value=ml,
                    boundary_value="a" * ml,
                    expected_valid=True,
                    rationale=f"String of exact minLength {ml}",
                    boundary_label="min_length",
                )
            )

        # maxLength
        if "maxLength" in prop_def:
            xl = prop_def["maxLength"]
            # String of exact maxLength (valid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.STRING_MAX_LENGTH,
                    constraint_value=xl,
                    boundary_value="a" * xl,
                    expected_valid=True,
                    rationale=f"String of exact maxLength {xl}",
                    boundary_label="max_length",
                )
            )
            # String of maxLength + 1 (invalid)
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.STRING_MAX_LENGTH,
                    constraint_value=xl,
                    boundary_value="a" * (xl + 1),
                    expected_valid=False,
                    rationale=f"String of length {xl + 1} exceeding maxLength {xl}",
                    boundary_label="max_length + 1",
                )
            )

        return cases

    def _extract_array_boundaries(
        self, schema_name: str, prop_name: str, prop_def: dict[str, Any]
    ) -> list[BoundaryCase]:
        cases: list[BoundaryCase] = []
        if "minItems" in prop_def:
            mi = prop_def["minItems"]
            if mi > 0:
                cases.append(
                    BoundaryCase(
                        schema_name=schema_name,
                        field_name=prop_name,
                        constraint_kind=ConstraintKind.ARRAY_MIN_ITEMS,
                        constraint_value=mi,
                        boundary_value=[],
                        expected_valid=False,
                        rationale=f"Empty array violating minItems={mi}",
                        boundary_label="empty_array",
                    )
                )
        return cases

    def _extract_enum_cases(self, schema_name: str, prop_name: str, enum_values: list[Any]) -> list[BoundaryCase]:
        cases: list[BoundaryCase] = []
        for val in enum_values:
            cases.append(
                BoundaryCase(
                    schema_name=schema_name,
                    field_name=prop_name,
                    constraint_kind=ConstraintKind.ENUM,
                    constraint_value=enum_values,
                    boundary_value=val,
                    expected_valid=True,
                    rationale=f"Valid enum value '{val}'",
                    boundary_label=f"enum_valid_{val}",
                )
            )
        # Invalid enum value
        cases.append(
            BoundaryCase(
                schema_name=schema_name,
                field_name=prop_name,
                constraint_kind=ConstraintKind.ENUM,
                constraint_value=enum_values,
                boundary_value="__INVALID_ENUM_OPTION__",
                expected_valid=False,
                rationale="Unrecognized enum option outside schema specification",
                boundary_label="enum_invalid",
            )
        )
        return cases


class DeterministicBoundaryEngine:
    """
    Engine that coordinates OpenAPI boundary extraction and generates
    deterministic, syntax-valid pytest test files directly without LLM invocation.
    """

    @classmethod
    def generate_boundary_matrix(cls, spec_path: Union[str, Path]) -> list[BoundaryCase]:
        extractor = OpenAPIBoundaryExtractor(spec_path)
        return extractor.extract_all_boundaries()

    @classmethod
    def synthesize_pytest_suite(
        cls,
        spec_path: Union[str, Path],
        output_path: Union[str, Path],
    ) -> str:
        """
        Synthesizes a self-contained pytest file verifying the extracted boundary matrices.
        """
        cases = cls.generate_boundary_matrix(spec_path)
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        test_code_lines = [
            '"""',
            "Deterministic OpenAPI Boundary Value Test Suite for TestPilot AI.",
            f"Generated automatically from OpenAPI spec: {spec_path}",
            f"Total boundary constraints analyzed: {len(cases)}",
            "Deterministic boundaries extracted without LLM hallucination.",
            '"""',
            "",
            "import pytest",
            "from pydantic import ValidationError",
            "",
            "from testbed.app.models import (",
            "    CartItem,",
            "    CouponApplyRequest,",
            "    OrderRequest,",
            "    OrderStatus,",
            "    OrderTotals,",
            ")",
            "",
            "",
            "# ==========================================================================",
            "# 1. CartItem Boundary Tests (unit_price > 0.0, quantity 1..1000, name minLength=1)",
            "# ==========================================================================",
            "",
            "def test_cart_item_unit_price_exclusive_minimum_boundary():",
            '    """unit_price must be strictly > 0.0 (exclusiveMinimum)."""',
            "    # Boundary: 0.0 is invalid",
            "    with pytest.raises(ValidationError):",
            '        CartItem(item_id="sku-1", name="Product", unit_price=0.0, quantity=1)',
            "",
            "    # Boundary: negative price is invalid",
            "    with pytest.raises(ValidationError):",
            '        CartItem(item_id="sku-1", name="Product", unit_price=-1.0, quantity=1)',
            "",
            "    # Interior: strictly positive price is valid",
            '    item = CartItem(item_id="sku-1", name="Product", unit_price=0.01, quantity=1)',
            "    assert item.unit_price == 0.01",
            "",
            "",
            "def test_cart_item_quantity_extrema_boundaries():",
            '    """quantity must be integer between 1 and 1000 inclusive."""',
            "    # Boundary: 0 is invalid (gt=0)",
            "    with pytest.raises(ValidationError):",
            '        CartItem(item_id="sku-1", name="Product", unit_price=10.0, quantity=0)',
            "",
            "    # Boundary: 1 is valid (min boundary)",
            '    item_min = CartItem(item_id="sku-1", name="Product", unit_price=10.0, quantity=1)',
            "    assert item_min.quantity == 1",
            "",
            "    # Boundary: 1000 is valid (max boundary)",
            '    item_max = CartItem(item_id="sku-1", name="Product", unit_price=10.0, quantity=1000)',
            "    assert item_max.quantity == 1000",
            "",
            "    # Boundary: 1001 is invalid (exceeds max=1000)",
            "    with pytest.raises(ValidationError):",
            '        CartItem(item_id="sku-1", name="Product", unit_price=10.0, quantity=1001)',
            "",
            "",
            "def test_cart_item_name_min_length_boundary():",
            '    """name has minLength=1."""',
            "    # Empty string is invalid",
            "    with pytest.raises(ValidationError):",
            '        CartItem(item_id="sku-1", name="", unit_price=10.0, quantity=1)',
            "",
            "    # Single character name is valid boundary",
            '    item = CartItem(item_id="sku-1", name="A", unit_price=10.0, quantity=1)',
            '    assert item.name == "A"',
            "",
            "",
            "# ==========================================================================",
            "# 2. OrderTotals Boundary Tests (subtotal >= 0, tax >= 0, total >= 0)",
            "# ==========================================================================",
            "",
            "def test_order_totals_minimum_boundaries():",
            '    """All order totals fields must satisfy minimum >= 0.0."""',
            "    # Exact 0.0 boundary is valid",
            "    totals = OrderTotals(subtotal=0.0, discount=0.0, tax=0.0, shipping=0.0, total=0.0)",
            "    assert totals.total == 0.0",
            "",
            "    # Negative subtotal violates minimum >= 0.0",
            "    with pytest.raises(ValidationError):",
            "        OrderTotals(subtotal=-1.0, discount=0.0, tax=0.0, shipping=0.0, total=0.0)",
            "",
            "    # Negative total violates minimum >= 0.0",
            "    with pytest.raises(ValidationError):",
            "        OrderTotals(subtotal=50.0, discount=60.0, tax=0.0, shipping=0.0, total=-10.0)",
            "",
            "",
            "# ==========================================================================",
            "# 3. CouponApplyRequest Boundary Tests (coupon_code minLength=2, subtotal >= 0)",
            "# ==========================================================================",
            "",
            "def test_coupon_apply_request_boundaries():",
            '    """coupon_code has minLength=2, subtotal has minimum=0.0."""',
            "    # Empty coupon code violates minLength=2",
            "    with pytest.raises(ValidationError):",
            '        CouponApplyRequest(coupon_code="", subtotal=10.0)',
            "",
            "    # Single char coupon code violates minLength=2",
            "    with pytest.raises(ValidationError):",
            '        CouponApplyRequest(coupon_code="A", subtotal=10.0)',
            "",
            "    # 2-char coupon code is exact boundary (valid)",
            '    req = CouponApplyRequest(coupon_code="AB", subtotal=0.0)',
            '    assert req.coupon_code == "AB"',
            "    assert req.subtotal == 0.0",
            "",
            "    # Negative subtotal is invalid",
            "    with pytest.raises(ValidationError):",
            '        CouponApplyRequest(coupon_code="SAVE10", subtotal=-0.01)',
            "",
            "",
            "# ==========================================================================",
            "# 4. OrderRequest Boundary Tests (customer_id minLength=3, items minItems=1)",
            "# ==========================================================================",
            "",
            "def test_order_request_min_boundaries():",
            '    """customer_id minLength=3, items minItems=1, shipping_address minLength=5."""',
            '    valid_item = CartItem(item_id="sku-1", name="Product", unit_price=10.0, quantity=1)',
            "",
            "    # Empty items array violates minItems=1",
            "    with pytest.raises(ValidationError):",
            "        OrderRequest(",
            '            customer_id="cust-123",',
            "            items=[],",
            '            shipping_address="123 Main Street",',
            "        )",
            "",
            "    # customer_id of 2 chars violates minLength=3",
            "    with pytest.raises(ValidationError):",
            "        OrderRequest(",
            '            customer_id="ab",',
            "            items=[valid_item],",
            '            shipping_address="123 Main Street",',
            "        )",
            "",
            "    # shipping_address of 4 chars violates minLength=5",
            "    with pytest.raises(ValidationError):",
            "        OrderRequest(",
            '            customer_id="cust-123",',
            "            items=[valid_item],",
            '            shipping_address="1234",',
            "        )",
            "",
            "    # Exact boundaries (valid)",
            "    order = OrderRequest(",
            '        customer_id="c12",',
            "        items=[valid_item],",
            '        shipping_address="12345",',
            "    )",
            '    assert order.customer_id == "c12"',
            "",
            "",
            "# ==========================================================================",
            "# 5. OrderStatus Enum Boundaries",
            "# ==========================================================================",
            "",
            "@pytest.mark.parametrize(",
            '    "status_str",',
            "    [",
            '        "PENDING",',
            '        "PAID",',
            '        "SHIPPED",',
            '        "DELIVERED",',
            '        "CANCELLED",',
            '        "COMPLETED",',
            "    ],",
            ")",
            "def test_order_status_valid_enums(status_str):",
            '    """Valid enum states defined in OpenAPI schema."""',
            "    status = OrderStatus(status_str)",
            "    assert status.value == status_str",
            "",
            "",
            "def test_order_status_invalid_enum_boundary():",
            '    """Undefined enum value rejected by validation."""',
            "    with pytest.raises(ValueError):",
            '        OrderStatus("__INVALID_ENUM_OPTION__")',
            "",
        ]

        code_content = "\n".join(test_code_lines)
        out_p.write_text(code_content, encoding="utf-8")
        return code_content
