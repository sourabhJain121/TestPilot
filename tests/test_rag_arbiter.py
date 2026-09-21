"""
Unit and integration tests for RAGArbiter and ArbitrationResult.
"""

from testpilot.rag.arbiter import ArbitrationResult, ArbitrationVerdict, RAGArbiter


def test_arbitration_result_schema():
    result = ArbitrationResult(
        test_name="test_dummy_failure",
        verdict=ArbitrationVerdict.TRUE_CODE_DEFECT,
        confidence=0.98,
        spec_clause="OpenAPI /orders/checkout total >= 0.0",
        explanation="OrderService produced negative total for large coupons",
        recommended_fix="Clamp discount to subtotal",
    )
    assert result.test_name == "test_dummy_failure"
    assert result.verdict == ArbitrationVerdict.TRUE_CODE_DEFECT
    assert result.verdict == "TRUE_CODE_DEFECT"
    assert result.confidence == 0.98
    assert "total >= 0.0" in result.spec_clause


def test_arbitration_result_three_valued_enum():
    assert ArbitrationVerdict.TRUE_CODE_DEFECT.value == "TRUE_CODE_DEFECT"
    assert ArbitrationVerdict.INVALID_TEST_ASSERTION.value == "INVALID_TEST_ASSERTION"
    assert ArbitrationVerdict.SPEC_AMBIGUITY_OR_DEFECT.value == "SPEC_AMBIGUITY_OR_DEFECT"

    ambiguity_result = ArbitrationResult(
        test_name="test_undefined_coupon_stacking",
        verdict=ArbitrationVerdict.SPEC_AMBIGUITY_OR_DEFECT,
        confidence=0.91,
        spec_clause="Specification silent on coupon stacking order",
        explanation="Spec does not define whether percentage or fixed discount applies first",
        recommended_fix="Clarify stacking priority in specification",
    )
    assert ambiguity_result.verdict == ArbitrationVerdict.SPEC_AMBIGUITY_OR_DEFECT
    assert ambiguity_result.verdict == "SPEC_AMBIGUITY_OR_DEFECT"


def test_arbitrate_negative_total_code_defect():
    arbiter = RAGArbiter()
    res = arbiter.arbitrate_failure(
        test_name="test_boundary_coupon_deficit_negative_total",
        error_message="AssertionError: assert -40.0 >= 0.0, coupon deficit produced negative total",
        function_source="def calculate_order_totals(...): total = (subtotal - discount) + tax + shipping",
    )

    assert isinstance(res, ArbitrationResult)
    assert res.verdict == ArbitrationVerdict.TRUE_CODE_DEFECT
    assert res.confidence >= 0.8
    assert "total" in res.explanation.lower() or "deficit" in res.explanation.lower() or "negative" in res.explanation.lower()


def test_arbitrate_tax_rounding_code_defect():
    arbiter = RAGArbiter()
    res = arbiter.arbitrate_failure(
        test_name="test_boundary_tax_fractional_precision_roundup",
        error_message="AssertionError: assert 0.82 == 0.83 (half-up rounding failed)",
        function_source="def calculate_tax(...): truncated_tax = int(taxable_amount * TAX_RATE * 100) / 100.0",
    )

    assert isinstance(res, ArbitrationResult)
    assert res.verdict == ArbitrationVerdict.TRUE_CODE_DEFECT
    assert "tax" in res.explanation.lower() or "round" in res.explanation.lower() or "truncat" in res.explanation.lower()


def test_arbitrate_illegal_state_transition_code_defect():
    arbiter = RAGArbiter()
    res = arbiter.arbitrate_failure(
        test_name="test_boundary_illegal_status_jump_cancelled_to_completed",
        error_message="AssertionError: Expected transition from terminal state CANCELLED to COMPLETED to be rejected with False, but code returned True",
        function_source="""def transition_order_status(current: OrderStatus, requested: OrderStatus):
    if current == OrderStatus.CANCELLED:
        if requested == OrderStatus.COMPLETED:
            return True, None
        return False, 'Cannot transition from CANCELLED'
    return True, None""",
    )

    assert isinstance(res, ArbitrationResult)
    assert res.verdict == ArbitrationVerdict.TRUE_CODE_DEFECT
    assert "transition" in res.explanation.lower() or "cancelled" in res.explanation.lower() or "status" in res.explanation.lower()


def test_arbitrate_invalid_test_assertion():
    arbiter = RAGArbiter()
    res = arbiter.arbitrate_failure(
        test_name="test_hallucinated_unknown_coupon_applied",
        error_message="AssertionError: assert discount == 50.0 (expected DISCOUNT coupon to give 50 off)",
        function_source="VALID_COUPONS = {'SAVE10': 0.10, 'SAVE20': 0.20, 'FLAT50': {'type': 'fixed', 'value': 50.0}}",
    )

    assert isinstance(res, ArbitrationResult)
    assert res.verdict == ArbitrationVerdict.INVALID_TEST_ASSERTION
    assert "coupon" in res.explanation.lower() or "invalid" in res.explanation.lower() or "test" in res.explanation.lower()


def test_arbitrate_spec_ambiguity_or_defect():
    arbiter = RAGArbiter()
    res = arbiter.arbitrate_failure(
        test_name="test_ambiguous_negative_subtotal_empty_cart_behavior",
        error_message="AssertionError: assert subtotal == 0.0 vs negative_subtotal underspecified",
        function_source="def calculate_subtotal(items): return sum(item.price for item in items)",
    )

    assert isinstance(res, ArbitrationResult)
    assert res.verdict == ArbitrationVerdict.SPEC_AMBIGUITY_OR_DEFECT
    assert "ambiguous" in res.explanation.lower() or "specification" in res.explanation.lower() or "silent" in res.explanation.lower()

