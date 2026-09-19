"""
FastAPI Microservice Testbed for TestPilot AI.
Provides RESTful endpoints for e-commerce cart, checkout, and order status lifecycle.
Exports OpenAPI 3.1 specification for Spec-as-Oracle automated testing.
"""

import json
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from testbed.app.models import (
    CartItem,
    CouponApplyRequest,
    CouponApplyResponse,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderTotals,
    StatusTransitionRequest,
    StatusTransitionResponse,
)
from testbed.app.services.order_service import OrderService

app = FastAPI(
    title="Testbed E-Commerce API",
    description="Modular microservice used as the target testing ground for TestPilot AI.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# In-memory mock storage
ORDERS_DB: dict[str, OrderResponse] = {}


@app.post("/cart/items/subtotal", response_model=dict[str, float], tags=["Cart"])
def calculate_subtotal(items: list[CartItem]):
    """Calculate raw subtotal for a list of items."""
    if not items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cart cannot be empty",
        )
    subtotal = OrderService.calculate_subtotal(items)
    return {"subtotal": subtotal}


@app.post("/orders/apply-coupon", response_model=CouponApplyResponse, tags=["Promotions"])
def apply_coupon(payload: CouponApplyRequest):
    """Validate coupon and calculate applicable discount amount."""
    discount = OrderService.calculate_discount(payload.coupon_code, payload.subtotal)
    if discount > 0.0:
        return CouponApplyResponse(
            valid=True,
            discount_amount=discount,
            message="Coupon applied successfully",
        )
    return CouponApplyResponse(
        valid=False,
        discount_amount=0.0,
        message="Invalid or non-applicable coupon code",
    )


@app.post("/orders/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, tags=["Orders"])
def create_order(payload: OrderRequest):
    """
    Calculate order totals and initialize a new pending order.
    Enforces that final total must never be negative.
    """
    order_id = str(uuid.uuid4())
    totals: OrderTotals = OrderService.calculate_order_totals(payload.items, payload.coupon_code)

    # OpenAPI / Spec rule: total must be >= 0.0
    if totals.total < 0.0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Integrity error: calculated order total {totals.total} cannot be negative",
        )

    order = OrderResponse(
        order_id=order_id,
        customer_id=payload.customer_id,
        status=OrderStatus.PENDING,
        items=payload.items,
        totals=totals,
        coupon_applied=payload.coupon_code if totals.discount > 0.0 else None,
    )
    ORDERS_DB[order_id] = order
    return order


@app.post("/orders/transition-status", response_model=StatusTransitionResponse, tags=["Orders"])
def transition_order_status(payload: StatusTransitionRequest):
    """Execute a lifecycle status transition for an order."""
    permitted, error = OrderService.transition_order_status(payload.current_status, payload.new_status)
    if not permitted:
        return StatusTransitionResponse(
            success=False,
            status=payload.current_status,
            error=error,
        )
    return StatusTransitionResponse(
        success=True,
        status=payload.new_status,
        error=None,
    )


def export_openapi_schema(output_path: str = "testbed/openapi.json"):
    """Export the OpenAPI 3.1 JSON schema to disk for RAG and Spec-as-Oracle ingestion."""
    schema = app.openapi()
    target_file = Path(output_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported OpenAPI schema to {output_path}")


if __name__ == "__main__":
    if "--export-openapi" in sys.argv:
        export_openapi_schema()
    else:
        import uvicorn
        uvicorn.run("testbed.app.main:app", host="0.0.0.0", port=8000, reload=True)
