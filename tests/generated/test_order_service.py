"""
TestPilot AI: Autonomous Boundary Test Suite for testbed/app/services/order_service.py
Prompt Technique: COT
Spec-as-Oracle Grounded Assertions targeting edge cases and boundary limits.
"""

import pytest
from pydantic import ValidationError
from testbed.app.models import CartItem, OrderStatus, OrderTotals
from testbed.app.services.order_service import (
    FREE_SHIPPING_THRESHOLD,
    STANDARD_SHIPPING_FEE,
    TAX_RATE,
    VALID_COUPONS,
    OrderService,
)

# Reasoning Trace Summary: The function `calculate_order_totals` is being analyzed using the Boundary Value Analysis (BVA) technique. The goal is to ensure that the function beh...

def test_empty_cart():
    from testbed.app.services.order_service import OrderService, CartItem
    items = []
    coupon_code = 'SAVE10'
    result = OrderService.calculate_order_totals(items, coupon_code)
    assert result.subtotal == 0.0
    assert result.discount == 0.0
    assert result.tax == 0.0
    assert result.shipping == 0.0
    assert result.total == 0.0

def test_subtotal_below_free_shipping_threshold():
    from testbed.app.services.order_service import OrderService, CartItem
    items = [CartItem(unit_price=49.99, quantity=1)]
    coupon_code = 'SAVE10'
    result = OrderService.calculate_order_totals(items, coupon_code)
    assert result.subtotal == 49.99
    assert result.discount == 4.999
    assert result.tax == 3.75
    assert result.shipping == 5.99
    assert result.total == 59.74

def test_subtotal_at_free_shipping_threshold():
    from testbed.app.services.order_service import OrderService, CartItem
    items = [CartItem(unit_price=50.00, quantity=1)]
    coupon_code = 'SAVE10'
    result = OrderService.calculate_order_totals(items, coupon_code)
    assert result.subtotal == 50.00
    assert result.discount == 5.00
    assert result.tax == 3.75
    assert result.shipping == 0.0
    assert result.total == 53.75

def test_subtotal_above_free_shipping_threshold():
    from testbed.app.services.order_service import OrderService, CartItem
    items = [CartItem(unit_price=50.01, quantity=1)]
    coupon_code = 'SAVE10'
    result = OrderService.calculate_order_totals(items, coupon_code)
    assert result.subtotal == 50.01
    assert result.discount == 5.001
    assert result.tax == 3.75
    assert result.shipping == 0.0
    assert result.total == 53.76

def test_valid_coupon_codes():
    from testbed.app.services.order_service import OrderService, CartItem
    items = [CartItem(unit_price=100.00, quantity=1)]
    coupon_code = 'SAVE20'
    result = OrderService.calculate_order_totals(items, coupon_code)
    assert result.subtotal == 100.00
    assert result.discount == 20.00
    assert result.tax == 6.60
    assert result.shipping == 0.0
    assert result.total == 86.60

def test_invalid_coupon_codes():
    from testbed.app.services.order_service import OrderService, CartItem
    items = [CartItem(unit_price=100.00, quantity=1)]
    coupon_code = 'INVALID'
    result = OrderService.calculate_order_totals(items, coupon_code)
    assert result.subtotal == 100.00
    assert result.discount == 0.0
    assert result.tax == 8.25
    assert result.shipping == 0.0
    assert result.total == 108.25

def test_negative_price():
    from testbed.app.services.order_service import OrderService, CartItem
    items = [CartItem(unit_price=-1.00, quantity=1)]
    coupon_code = 'SAVE10'
    with pytest.raises(ValidationError):
        OrderService.calculate_order_totals(items, coupon_code)
