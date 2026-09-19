"""
Integration tests for the FastAPI Testbed microservice.
Validates RESTful contracts, boundary checks, and proves the existence of the 3 seeded bugs.
"""

from fastapi.testclient import TestClient

from testbed.app.main import app
from testbed.app.models import OrderStatus
from testbed.app.services.order_service import OrderService

client = TestClient(app)


def test_cart_subtotal_valid():
    response = client.post(
        "/cart/items/subtotal",
        json=[
            {"item_id": "item-1", "name": "Mechanical Keyboard", "unit_price": 75.50, "quantity": 2},
            {"item_id": "item-2", "name": "Mousepad", "unit_price": 14.99, "quantity": 1},
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["subtotal"] == 165.99


def test_apply_valid_and_invalid_coupons():
    resp_valid = client.post(
        "/orders/apply-coupon",
        json={"coupon_code": "SAVE10", "subtotal": 100.00},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["valid"] is True
    assert resp_valid.json()["discount_amount"] == 10.00

    resp_invalid = client.post(
        "/orders/apply-coupon",
        json={"coupon_code": "EXPIRED99", "subtotal": 100.00},
    )
    assert resp_invalid.status_code == 200
    assert resp_invalid.json()["valid"] is False


def test_bug_1_discount_deficit_negative_total():
    """
    BUG 1: Fixed discount FLAT50 ($50) applied to a $20 order.
    The service calculates total = (20 - 50) + 0 + shipping = -24.01.
    Pydantic's Spec-as-Oracle constraint (total >= 0.0) catches this and rejects it with ValidationError!
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as excinfo:
        OrderService.calculate_order_totals(
            items=[
                {"item_id": "item-1", "name": "Notebook", "unit_price": 20.00, "quantity": 1},
            ],
            coupon_code="FLAT50",
        )
    assert "Input should be greater than or equal to 0" in str(excinfo.value)


def test_bug_2_tax_truncation_rounding():
    """
    BUG 2: 10.06 * 0.0825 = 0.82995.
    Proper half-up rounding gives 0.83.
    Bug truncates to 0.82.
    """
    tax = OrderService.calculate_tax(10.06)
    # The bug produces 0.82 instead of 0.83:
    assert tax == 0.82, "Demonstrating Bug 2: Floating point tax truncated to 0.82 instead of 0.83"


def test_bug_3_illegal_status_jump_cancelled_to_completed():
    """
    BUG 3: State machine allows CANCELLED to jump directly to COMPLETED.
    """
    allowed, error = OrderService.transition_order_status(
        current=OrderStatus.CANCELLED,
        requested=OrderStatus.COMPLETED,
    )
    # The bug erroneously permits this transition:
    assert allowed is True, "Demonstrating Bug 3: Transition from CANCELLED to COMPLETED erroneously permitted"
