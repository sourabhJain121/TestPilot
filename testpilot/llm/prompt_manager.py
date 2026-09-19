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
You must adhere to the Spec-as-Oracle philosophy:
- Test exact boundary limits: zero values, empty structures, negative values, and precision bounds.
- Never mock away business logic flaws.
- Output MUST be valid JSON conforming strictly to the requested schema.
"""

    COT_REASONING_STEPS = """
Follow this formal 4-phase Chain-of-Thought reasoning protocol:
PHASE 1: CONTRACT & SPECIFICATION EXTRACTION
Identify all business rules, invariants, and constraints (e.g. total >= 0.0, valid state transitions, precision requirements).

PHASE 2: EQUIVALENCE PARTITIONING
Define valid input partitions and invalid input partitions.

PHASE 3: BOUNDARY VALUE ANALYSIS (BVA)
Identify the exact boundary points on the edges (e.g., threshold - 0.01, threshold, threshold + 0.01; 0, -1; empty list).

PHASE 4: TEST SYNTHESIS
Produce targeted test case specifications that verify whether the implementation adheres to these boundaries.
"""

    FEW_SHOT_EXEMPLARS = """
Example Boundary Test Case 1:
{
  "test_name": "test_calculate_discount_exceeds_subtotal_negative_boundary",
  "target_function": "calculate_discount",
  "boundary_focus": "Fixed discount exceeding subtotal causing potential negative net total",
  "input_values": {"subtotal": 20.0, "coupon_code": "FLAT50"},
  "expected_behavior": "Should cap discount at subtotal (20.0) or ensure net payable amount is not negative",
  "rationale": "Applying a $50 fixed coupon on a $20 order must not produce a negative total balance.",
  "code": "def test_calculate_discount_exceeds_subtotal():\\n    totals = OrderService.calculate_order_totals([CartItem(item_id='1', name='Item', unit_price=20.0, quantity=1)], coupon_code='FLAT50')\\n    assert totals.total >= 0.0, f'Order total cannot be negative: {totals.total}'"
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
