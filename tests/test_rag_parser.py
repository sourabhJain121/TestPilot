"""
Unit and integration tests for SpecParser (OpenAPI and Markdown chunking).
"""

from pathlib import Path

from testpilot.rag.parser import SpecChunk, SpecParser


def test_parse_openapi_endpoints_and_schemas():
    openapi_file = "testbed/openapi.json"
    assert Path(openapi_file).exists(), "testbed/openapi.json must exist"

    chunks = SpecParser.parse_openapi(openapi_file)
    assert len(chunks) > 0, "Parser must extract chunks from OpenAPI"

    # Verify endpoint chunks
    endpoint_chunks = [c for c in chunks if c.metadata.get("type") == "endpoint"]
    assert len(endpoint_chunks) >= 3, "Must extract at least 3 endpoint operations"

    orders_checkout = next((c for c in endpoint_chunks if "/orders/checkout" in c.content), None)
    assert orders_checkout is not None
    assert orders_checkout.metadata["source"] == "openapi"
    assert orders_checkout.metadata["method"] == "POST"
    assert orders_checkout.metadata["endpoint"] == "/orders/checkout"
    assert "201" in orders_checkout.content
    assert "422" in orders_checkout.content

    # Verify schema chunks
    schema_chunks = [c for c in chunks if c.metadata.get("type") == "schema"]
    assert len(schema_chunks) >= 2, "Must extract schema models"
    cart_item_chunk = next((c for c in schema_chunks if c.metadata.get("model_name") == "CartItem"), None)
    assert cart_item_chunk is not None
    assert "unit_price" in cart_item_chunk.content


def test_parse_markdown_header_hierarchy(tmp_path):
    md_content = """# Test Technical Specification
This is an introductory overview.

## Section 1: Business Rules
- Rule 1: Shipping is free over $50.
- Rule 2: Taxes must round half-up.

### Subsection 1.1: Coupon Discounts
SAVE10 provides 10% off.
SAVE20 provides 20% off.

## Section 2: Order State Machine
Orders cannot transition from CANCELLED to COMPLETED.
"""
    doc_path = tmp_path / "spec_test.md"
    doc_path.write_text(md_content, encoding="utf-8")

    chunks = SpecParser.parse_markdown(str(doc_path))
    assert len(chunks) >= 3

    # Check deterministic chunk IDs
    for chunk in chunks:
        assert isinstance(chunk, SpecChunk)
        assert chunk.id.startswith("doc_")
        assert chunk.metadata["source"] == "markdown"

    coupon_chunk = next((c for c in chunks if "SAVE10" in c.content), None)
    assert coupon_chunk is not None
    assert "Subsection 1.1: Coupon Discounts" in coupon_chunk.metadata.get("header", "")


def test_parse_all_combines_specs():
    chunks = SpecParser.parse_all(openapi_path="testbed/openapi.json", docs_dir="docs")
    assert len(chunks) > 5
    sources = {c.metadata["source"] for c in chunks}
    assert "openapi" in sources
    assert "markdown" in sources
