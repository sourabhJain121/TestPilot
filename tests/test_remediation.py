"""
Unit and integration tests for RemediationPatcher (Sweep.dev autonomous repair bot).
"""

import sys
from pathlib import Path

from testpilot.rag.arbiter import ArbitrationResult
from testpilot.remediation.patcher import RemediationPatcher, RemediationResult


def test_remediation_result_model():
    result = RemediationResult(
        target_file="testbed/app/services/order_service.py",
        patch_generated=True,
        verified_in_sandbox=True,
        unified_diff="--- a/file.py\n+++ b/file.py\n",
        message="Patch created",
    )
    assert result.target_file == "testbed/app/services/order_service.py"
    assert result.patch_generated is True
    assert result.verified_in_sandbox is True
    assert "---" in result.unified_diff


def test_generate_remediation_patch_for_discount_deficit(tmp_path):
    # Create a temporary defective source file
    source_content = """# Order Service Defective Snippet
def calculate_discount(subtotal: float, coupon_code: str):
    rule = {"type": "fixed", "value": 50.0}
    return rule["value"]

def calculate_order_totals(subtotal: float, discount: float, tax: float, shipping: float):
    total = round((subtotal - discount) + tax + shipping, 2)
    return total
"""
    target_file = tmp_path / "order_service_defect.py"
    target_file.write_text(source_content, encoding="utf-8")

    arbitration = ArbitrationResult(
        test_name="test_boundary_coupon_deficit_negative_total",
        verdict="TRUE_CODE_DEFECT",
        confidence=0.99,
        spec_clause="OpenAPI /orders/checkout: total must be >= 0.0",
        explanation="Coupon deficit produced negative total balance.",
        recommended_fix="Clamp fixed discount to subtotal: min(subtotal, rule['value']) and clamp total >= 0.0",
    )

    patcher = RemediationPatcher()
    result = patcher.generate_remediation_patch(
        target_file_path=str(target_file),
        arbitration=arbitration,
        test_command=[sys.executable, "-c", "import sys; sys.exit(0)"],
    )

    assert result.patch_generated is True
    assert result.verified_in_sandbox is True
    assert len(result.unified_diff) > 0
    assert Path("remediation.patch").exists()


def test_remediation_nonexistent_file():
    arbitration = ArbitrationResult(
        test_name="dummy_test",
        verdict="TRUE_CODE_DEFECT",
        confidence=0.9,
        spec_clause="Spec",
        explanation="Issue",
        recommended_fix="Fix",
    )
    patcher = RemediationPatcher()
    result = patcher.generate_remediation_patch(
        target_file_path="nonexistent_file_xyz.py",
        arbitration=arbitration,
    )
    assert result.patch_generated is False
    assert "does not exist" in result.message
