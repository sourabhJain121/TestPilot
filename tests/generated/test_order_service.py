"""
TestPilot AI: Autonomous Boundary Test Suite for testbed/app/services/order_service.py
Prompt Technique: COT
Spec-as-Oracle Grounded Assertions targeting edge cases and boundary limits.
"""

import pytest
from testbed.app.models import CartItem, OrderStatus, OrderTotals
from testbed.app.services.order_service import OrderService, VALID_COUPONS

# Reasoning Trace Summary: The function `calculate_order_totals` has several boundary conditions that need to be thoroughly tested to ensure the implementation adheres to the sp...

def test_empty_cart():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=0.0, discount=0.0, tax=0.0, shipping=0.0, total=0.0)

def test_zero_subtotal():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': 0.0, 'quantity': 1} ], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=0.0, discount=0.0, tax=0.0, shipping=0.0, total=0.0)

def test_negative_subtotal():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': -1.0, 'quantity': 1} ], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=0.0, discount=0.0, tax=0.0, shipping=0.0, total=0.0)

def test_valid_coupon_code():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': 100.0, 'quantity': 1} ], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=100.0, discount=10.0, tax=7.25, shipping=5.99, total=92.24)

def test_invalid_coupon_code():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': 100.0, 'quantity': 1} ], coupon_code='DISCOUNT')
    assert result == OrderTotals(subtotal=100.0, discount=0.0, tax=8.25, shipping=5.99, total=114.24)

def test_free_shipping():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': 50.0, 'quantity': 1} ], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=50.0, discount=5.0, tax=3.81, shipping=0.0, total=48.81)

def test_standard_shipping():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': 49.0, 'quantity': 1} ], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=49.0, discount=4.9, tax=3.74, shipping=5.99, total=58.73)

def test_sales_tax():
    from testbed.app.services.order_service import OrderService, CartItem, OrderTotals
    result = OrderService.calculate_order_totals(items=[ {'price': 100.0, 'quantity': 1} ], coupon_code='SAVE10')
    assert result == OrderTotals(subtotal=100.0, discount=10.0, tax=7.25, shipping=5.99, total=92.24)
