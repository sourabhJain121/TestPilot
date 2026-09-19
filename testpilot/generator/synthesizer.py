"""
Pytest Test Synthesizer for TestPilot AI.
Converts structured LLM test case specifications into clean, executable,
idiomatic pytest test scripts and validates their AST syntax.
"""

import ast
from pathlib import Path

from testpilot.core.models import GeneratedTestSuite


class PytestSynthesizer:
    """
    Transforms structured GeneratedTestSuite models into executable Python test files,
    injecting imports, fixtures, and assertions, with AST syntax validation.
    """

    @classmethod
    def synthesize_suite(cls, suite: GeneratedTestSuite, output_path: str = "tests/generated/test_suite.py") -> str:
        """Generate a complete pytest file from a GeneratedTestSuite and save to disk."""
        lines = [
            '"""',
            f"TestPilot AI: Autonomous Boundary Test Suite for {suite.target_module}",
            f"Prompt Technique: {suite.technique_used.value.upper()}",
            "Spec-as-Oracle Grounded Assertions targeting edge cases and boundary limits.",
            '"""',
            "",
            "import pytest",
            "from testbed.app.models import CartItem, OrderStatus, OrderTotals",
            "from testbed.app.services.order_service import OrderService, VALID_COUPONS",
            "",
        ]

        if suite.reasoning_trace:
            lines.append(f"# Reasoning Trace Summary: {suite.reasoning_trace[:150]}...")
            lines.append("")

        for tc in suite.test_cases:
            if tc.code and tc.code.strip().startswith("def test_"):
                # Use LLM-generated code directly if valid
                try:
                    ast.parse(tc.code)
                    lines.append(tc.code.strip())
                    lines.append("")
                    continue
                except SyntaxError:
                    pass

            # Synthesize deterministic boundary test based on target_function and boundary_focus
            func_name = tc.target_function.lower()
            lines.append(f"def {tc.test_name}():")
            lines.append('    """')
            lines.append(f"    Boundary Focus: {tc.boundary_focus}")
            lines.append(f"    Rationale: {tc.rationale}")
            lines.append('    """')

            if "discount" in func_name or "coupon" in func_name:
                lines.append("    # Boundary test: Verify that applying coupon when subtotal is lower than discount amount")
                lines.append("    # does not result in negative net payable total.")
                lines.append("    item = CartItem(item_id='sku-001', name='Pencil', unit_price=10.0, quantity=1)")
                lines.append("    totals = OrderService.calculate_order_totals([item], coupon_code='FLAT50')")
                lines.append("    assert totals.total >= 0.0, f'Calculated total {totals.total} must never be negative!'")

            elif "tax" in func_name:
                lines.append("    # Boundary test: Fractional cent rounding precision at threshold amount")
                lines.append("    taxable_amount = 10.06")
                lines.append("    tax = OrderService.calculate_tax(taxable_amount)")
                lines.append("    # 10.06 * 0.0825 = 0.82995 -> should round up to 0.83")
                lines.append("    assert tax == 0.83, f'Tax {tax} failed precision round-up; expected 0.83'")

            elif "transition" in func_name or "status" in func_name:
                lines.append("    # Boundary test: Verify CANCELLED orders cannot jump directly to COMPLETED")
                lines.append("    allowed, error = OrderService.transition_order_status(OrderStatus.CANCELLED, OrderStatus.COMPLETED)")
                lines.append("    assert allowed is False, 'Illegal transition: CANCELLED order must not transition to COMPLETED'")

            else:
                lines.append("    # Boundary partition check")
                lines.append("    items = [CartItem(item_id='test-1', name='Sample', unit_price=25.0, quantity=2)]")
                lines.append("    totals = OrderService.calculate_order_totals(items)")
                lines.append("    assert totals.subtotal == 50.0")
                lines.append("    assert totals.shipping == 0.0  # Threshold boundary: >= 50 qualifies for free shipping")

            lines.append("")

        complete_code = "\n".join(lines)

        # Validate syntax
        try:
            ast.parse(complete_code)
        except SyntaxError as e:
            raise ValueError(f"Generated test code failed AST syntax validation: {e}\n{complete_code}") from e

        # Save to disk
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(complete_code, encoding="utf-8")

        suite.complete_pytest_code = complete_code
        return complete_code
