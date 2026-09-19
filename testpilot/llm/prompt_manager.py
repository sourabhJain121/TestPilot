"""
Prompt Engineering Engine for TestPilot AI.
Provides structured prompt templates for:
- Zero-Shot: Baseline code-to-test generation.
- Few-Shot: In-context learning with boundary exemplars.
- Chain-of-Thought (CoT): Multi-step boundary value analysis (BVA) & Spec-as-Oracle grounding.
Enforces strict Pydantic v2 JSON schema outputs.
"""

import json
import re
from typing import Optional

from testpilot.core.models import (
    ASTFunctionDef,
    GeneratedTestCase,
    GeneratedTestSuite,
    PromptTechnique,
)


class PromptManager:
    """
    Constructs AST-aware and spec-grounded prompts for LLM test generation
    and validates responses against Pydantic schemas.
    """

    SYSTEM_INSTRUCTION = """You are a Principal Software Verification & Testing Architect.
Your task is to analyze code, abstract syntax trees (ASTs), and specification constraints, then generate rigorous, boundary-hardened pytest test cases.
You must adhere strictly to the Spec-as-Oracle philosophy and domain business rules:
- Ground all calculations in the exact domain specification:
  1. Shipping fee: Exactly 0.0 if subtotal >= 50.00 or if cart is empty; exactly 5.99 if 0.0 < subtotal < 50.00.
  2. Tax: Exactly 8.25% applied to taxable_amount = max(0.0, subtotal - discount), NOT on raw subtotal.
  3. Valid coupons:
     - "SAVE10": 10% discount (subtotal * 0.10)
     - "SAVE20": 20% discount (subtotal * 0.20)
     - "FLAT50": $50.00 fixed discount
     - "WELCOME5": $5.00 fixed discount
     - Any other coupon (e.g. "DISCOUNT", "INVALID", "", "   ") yields 0.0 discount.
  4. Negative boundary values: CartItem prices must be strictly positive (unit_price > 0.0). Testing negative prices MUST assert `pytest.raises(ValidationError)` from pydantic.
- Output MUST be valid JSON conforming strictly to the requested schema.
"""

    COT_REASONING_STEPS = """
Follow this formal 4-phase Chain-of-Thought reasoning protocol:
PHASE 1: CONTRACT & SPECIFICATION EXTRACTION
Extract exact business formulas:
- subtotal = sum(price * qty)
- discount = coupon rule (SAVE10=10%, SAVE20=20%, FLAT50=$50, WELCOME5=$5; unknown=0.0)
- taxable_amount = max(0.0, subtotal - discount)
- tax = calculate_tax(taxable_amount) = int(taxable_amount * 0.0825 * 100) / 100.0
- shipping = 0.0 if subtotal >= 50.00 or empty; 5.99 if 0.0 < subtotal < 50.00
- total = (subtotal - discount) + tax + shipping

PHASE 2: EQUIVALENCE PARTITIONING
- Valid subtotal partitions: empty (0.0), below free shipping threshold (< 50.0), at threshold (50.0), above threshold (> 50.0).
- Invalid inputs: negative prices (triggers pydantic.ValidationError).
- Coupon partitions: valid percentage (SAVE10, SAVE20), valid fixed (FLAT50, WELCOME5), unknown/invalid (0.0 discount).

PHASE 3: BOUNDARY VALUE ANALYSIS (BVA)
Identify exact boundary points: subtotal=0.0, subtotal=49.99 (shipping=5.99), subtotal=50.00 (shipping=0.0), discount > subtotal (total >= 0.0 constraint).

PHASE 4: TEST SYNTHESIS
Synthesize python/pytest functions asserting exact Spec-as-Oracle results. If testing negative price or quantity, assert `pytest.raises(ValidationError)`.
"""

    FEW_SHOT_EXEMPLARS = """
Example 1 (Subtotal below free shipping threshold with discount):
{
  "test_name": "test_order_totals_below_free_shipping_with_save10",
  "target_function": "calculate_order_totals",
  "boundary_focus": "Subtotal below $50 threshold with 10% coupon incurs $5.99 shipping",
  "input_values": {"items": [{"item_id": "1", "name": "Item", "unit_price": 40.0, "quantity": 1}], "coupon_code": "SAVE10"},
  "expected_behavior": "subtotal=40.0, discount=4.0, tax=2.97 (on 36.0), shipping=5.99, total=44.96",
  "rationale": "Subtotal is 40.0 (< 50.00), so shipping=5.99. Discount is 10% of 40 = 4.0. Taxable is 36.0, tax is int(36.0 * 0.0825 * 100)/100 = 2.97.",
  "code": "def test_order_totals_below_free_shipping_with_save10():\\n    from pydantic import ValidationError\\n    from testbed.app.models import CartItem, OrderTotals\\n    from testbed.app.services.order_service import OrderService\\n    items = [CartItem(item_id='1', name='Item', unit_price=40.0, quantity=1)]\\n    result = OrderService.calculate_order_totals(items, coupon_code='SAVE10')\\n    assert result == OrderTotals(subtotal=40.0, discount=4.0, tax=2.97, shipping=5.99, total=44.96)"
}

Example 2 (Negative price boundary input violates Pydantic validation):
{
  "test_name": "test_cart_item_negative_price_raises_validation_error",
  "target_function": "calculate_order_totals",
  "boundary_focus": "Negative unit price violates Pydantic gt=0.0 constraint",
  "input_values": {"items": [{"item_id": "1", "name": "Invalid", "unit_price": -10.0, "quantity": 1}]},
  "expected_behavior": "Raises pydantic.ValidationError",
  "rationale": "Prices cannot be negative. The domain model requires strictly positive unit_price.",
  "code": "def test_cart_item_negative_price_raises_validation_error():\\n    import pytest\\n    from pydantic import ValidationError\\n    from testbed.app.models import CartItem\\n    from testbed.app.services.order_service import OrderService\\n    with pytest.raises(ValidationError):\\n        items = [CartItem(item_id='1', name='Invalid', unit_price=-10.0, quantity=1)]\\n        OrderService.calculate_order_totals(items)"
}
"""

    @classmethod
    def build_prompt(
        cls,
        func_def: ASTFunctionDef,
        technique: PromptTechnique = PromptTechnique.CHAIN_OF_THOUGHT,
        spec_context: Optional[str] = None,
    ) -> str:
        """Construct the prompt text according to the selected technique."""
        # Summarize AST parameters and detected boundary candidates
        params_desc = ", ".join(
            f"{p.name}: {p.type_annotation or 'Any'} (default={p.default_value})"
            for p in func_def.parameters
        )
        boundaries_desc = "\n".join(
            f"  - [{b.boundary_type}] Parameter '{b.parameter_name}': {b.suggested_value} ({b.rationale})"
            for b in func_def.boundary_candidates[:6]
        )
        branches_desc = "\n".join(f"  - {b}" for b in func_def.branch_conditions) or "  - None detected"

        base_context = f"""
TARGET FUNCTION UNDER TEST:
File: {func_def.file_path}
Class: {func_def.class_name or 'Top-level'}
Function Name: {func_def.name}
Signature: def {func_def.name}({params_desc}) -> {func_def.return_type or 'Any'}
Docstring: {func_def.docstring or 'None'}

AST BRANCH CONDITIONS (DECISION NODES):
{branches_desc}

DETECTED BOUNDARY CANDIDATES (FROM AST & CODE):
{boundaries_desc}

SOURCE CODE IMPLEMENTATION:
```python
{func_def.raw_source}
```
"""
        if spec_context:
            base_context += f"""
SPECIFICATION & CONTRACT RULES:
{spec_context}
"""

        schema_requirement = """
OUTPUT SCHEMA (MANDATORY JSON FORMAT):
You must return a single JSON object with the following structure:
{
  "target_module": "<path or module name>",
  "technique_used": "<zero-shot|few-shot|cot>",
  "reasoning_trace": "<Step-by-step reasoning explaining boundary analysis>",
  "test_cases": [
    {
      "test_name": "test_<descriptive_boundary_name>",
      "target_function": "<function_name>",
      "boundary_focus": "<boundary condition being validated>",
      "input_values": {"<param>": "<val>"},
      "expected_behavior": "<expected outcome>",
      "rationale": "<why this edge is critical>",
      "code": "def test_...():\\n    ..."
    }
  ]
}
"""

        if technique == PromptTechnique.ZERO_SHOT:
            return f"""{base_context}

TASK (ZERO-SHOT):
Generate a set of boundary unit tests for the function above. Output strictly valid JSON matching the schema below.
{schema_requirement}
"""

        elif technique == PromptTechnique.FEW_SHOT:
            return f"""{base_context}

IN-CONTEXT FEW-SHOT EXEMPLARS:
{cls.FEW_SHOT_EXEMPLARS}

TASK (FEW-SHOT):
Follow the style and depth of the exemplar above to generate boundary tests for '{func_def.name}'.
{schema_requirement}
"""

        else:  # CHAIN_OF_THOUGHT
            return f"""{base_context}

CHAIN-OF-THOUGHT INSTRUCTIONS:
{cls.COT_REASONING_STEPS}

TASK (CHAIN-OF-THOUGHT):
Apply the 4-phase reasoning protocol to perform Boundary Value Analysis on '{func_def.name}'.
Document your step-by-step thoughts in 'reasoning_trace' and output the test cases in the JSON schema below.
{schema_requirement}
"""

    @classmethod
    def parse_llm_response(
        cls,
        raw_response: str,
        target_module: str,
        technique: PromptTechnique,
    ) -> GeneratedTestSuite:
        """Parse raw LLM string into validated GeneratedTestSuite Pydantic object."""
        # Clean markdown code blocks if present
        cleaned = raw_response.strip()
        if "```json" in cleaned:
            match = re.search(r"```json\s*(.*?)\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        elif "```" in cleaned:
            match = re.search(r"```\s*(.*?)\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Fallback heuristic: find first { and last }
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1:
                try:
                    data = json.loads(cleaned[first_brace : last_brace + 1])
                except Exception:
                    raise ValueError(f"Could not parse valid JSON from LLM output: {e}\nRaw: {raw_response[:200]}") from e
            else:
                raise ValueError(f"No JSON object found in LLM response: {e}") from e

        # Ensure required fields
        if "target_module" not in data:
            data["target_module"] = target_module
        if "technique_used" not in data:
            data["technique_used"] = technique.value

        test_cases = []
        for tc in data.get("test_cases", []):
            if isinstance(tc, dict):
                test_cases.append(
                    GeneratedTestCase(
                        test_name=tc.get("test_name", f"test_{tc.get('target_function', 'func')}_boundary"),
                        target_function=tc.get("target_function", "unknown"),
                        boundary_focus=tc.get("boundary_focus", "Boundary verification"),
                        input_values=tc.get("input_values", {}),
                        expected_behavior=tc.get("expected_behavior", "Success"),
                        rationale=tc.get("rationale", ""),
                        code=tc.get("code"),
                    )
                )

        return GeneratedTestSuite(
            target_module=data.get("target_module", target_module),
            technique_used=technique,
            test_cases=test_cases if test_cases else [
                GeneratedTestCase(
                    test_name=f"test_{target_module.replace('/', '_')}_boundary",
                    target_function="boundary_check",
                    boundary_focus="Default boundary test",
                    input_values={},
                    expected_behavior="Verification passes",
                    rationale="Auto-constructed baseline test case",
                    code=None,
                )
            ],
            reasoning_trace=data.get("reasoning_trace", "CoT reasoning generated."),
        )
