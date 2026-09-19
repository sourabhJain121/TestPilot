"""
Domain models and Pydantic v2 schemas for the TestPilot FastAPI testbed.
Enforces strict validation, field boundaries, and OpenAPI contracts.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class CartItem(BaseModel):
    item_id: str = Field(default="item-1", description="Unique product SKU or identifier")
    name: str = Field(default="Test Item", min_length=1, description="Product display name")
    unit_price: float = Field(..., gt=0.0, description="Price per unit in USD; must be strictly positive")
    quantity: int = Field(default=1, gt=0, le=1000, description="Number of items ordered (1 to 1000)")


class OrderTotals(BaseModel):
    subtotal: float = Field(..., ge=0.0, description="Sum of item prices before discount and tax")
    discount: float = Field(default=0.0, ge=0.0, description="Discount amount applied")
    tax: float = Field(..., ge=0.0, description="Calculated sales tax")
    shipping: float = Field(default=0.0, ge=0.0, description="Shipping fee")
    total: float = Field(..., ge=0.0, description="Final payable amount; must never be negative")


class OrderRequest(BaseModel):
    customer_id: str = Field(..., min_length=3, description="Customer account ID")
    items: list[CartItem] = Field(..., min_length=1, description="List of items in the cart")
    shipping_address: str = Field(..., min_length=5, description="Physical shipping address")
    coupon_code: Optional[str] = Field(default=None, description="Optional promotional discount code")


class OrderResponse(BaseModel):
    order_id: str = Field(..., description="Generated UUID for the order")
    customer_id: str = Field(..., description="Customer account ID")
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current lifecycle status")
    items: list[CartItem] = Field(..., description="Items included in the order")
    totals: OrderTotals = Field(..., description="Detailed breakdown of costs")
    coupon_applied: Optional[str] = Field(default=None, description="Applied coupon code if valid")


class CouponApplyRequest(BaseModel):
    coupon_code: str = Field(..., min_length=2, description="Promotional code")
    subtotal: float = Field(..., ge=0.0, description="Cart subtotal before discount")


class CouponApplyResponse(BaseModel):
    valid: bool = Field(..., description="Whether the coupon is accepted")
    discount_amount: float = Field(default=0.0, ge=0.0, description="Discount value in dollars")
    message: str = Field(..., description="Explanation or rejection reason")


class StatusTransitionRequest(BaseModel):
    current_status: OrderStatus = Field(..., description="Current status of the order")
    new_status: OrderStatus = Field(..., description="Requested new status")
    reason: Optional[str] = Field(default=None, description="Optional audit log explanation")


class StatusTransitionResponse(BaseModel):
    success: bool = Field(..., description="Whether the transition was permitted")
    status: OrderStatus = Field(..., description="Resulting order status")
    error: Optional[str] = Field(default=None, description="Error message if transition was rejected")
