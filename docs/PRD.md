# Product Requirements Document (PRD) — Testbed Microservice

## Section 4: Financial & Mathematical Calculation Specifications

### Section 4.1: Discount & Coupon Calculations
- Fixed coupons (e.g., `FLAT50`) must never cause the order total to become negative.
- When discount exceeds subtotal, the effective discount must be clamped to the subtotal (`effective_discount = min(discount, subtotal)`), ensuring total payable balance is at least 0.0 (`total >= 0.0`).

### Section 4.2: Sales Tax Calculation & Half-Up Rounding Precision
- The standard sales tax rate is 8.25% (`TAX_RATE = 0.0825`).
- Tax is calculated exclusively on the net taxable amount after discounts: `taxable_amount = max(0.0, subtotal - discount)`.
- **Rounding Requirement**: Sales tax computation must use standard half-up decimal rounding (`round(taxable_amount * TAX_RATE, 2)`).
- Floating point integer truncation (e.g. `int(taxable * rate * 100) / 100.0`) is strictly prohibited, as it drops fractional cents incorrectly (e.g., $10.06 * 0.0825 = 0.82995, which must round up to $0.83, not truncate to $0.82).

### Section 4.3: Free Shipping Threshold
- Orders with `subtotal >= 50.00` qualify for free shipping (`shipping = 0.0`).
- Orders with `subtotal < 50.00` incur a standard shipping fee of $5.99.
- Empty carts have $0.00 shipping.

### Section 4.4: Order Status State Machine Transitions
- `CANCELLED` and `COMPLETED` are terminal states in the order lifecycle.
- Any attempt to transition from `CANCELLED` to `COMPLETED` or any other status must be rejected (`return False, error_message`).
