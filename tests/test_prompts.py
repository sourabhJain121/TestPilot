"""
Unit tests for PromptManager and schema parsing.
"""

from testpilot.ast_engine.treesitter_parser import ASTDiffParser
from testpilot.core.models import PromptTechnique
from testpilot.llm.prompt_manager import PromptManager


def test_build_prompt_techniques():
    funcs = ASTDiffParser.parse_file("testbed/app/services/order_service.py")
    func = next(f for f in funcs if f.name == "calculate_discount")

    zero_shot_prompt = PromptManager.build_prompt(func, technique=PromptTechnique.ZERO_SHOT)
    assert "ZERO-SHOT" in zero_shot_prompt
    assert "calculate_discount" in zero_shot_prompt

    few_shot_prompt = PromptManager.build_prompt(func, technique=PromptTechnique.FEW_SHOT)
    assert "FEW-SHOT EXEMPLARS" in few_shot_prompt

    cot_prompt = PromptManager.build_prompt(func, technique=PromptTechnique.CHAIN_OF_THOUGHT)
    assert "BOUNDARY VALUE ANALYSIS (BVA)" in cot_prompt
    assert "PHASE 1: CONTRACT" in cot_prompt


def test_parse_llm_response_valid_json():
    sample_response = """
    ```json
    {
      "target_module": "testbed.app.services.order_service",
      "technique_used": "cot",
      "reasoning_trace": "BVA analysis performed for negative discount bounds.",
      "test_cases": [
        {
          "test_name": "test_discount_boundary",
          "target_function": "calculate_discount",
          "boundary_focus": "subtotal equals discount",
          "input_values": {"subtotal": 50.0, "coupon_code": "FLAT50"},
          "expected_behavior": "total is 0.0",
          "rationale": "Exact equality boundary condition"
        }
      ]
    }
    ```
    """
    suite = PromptManager.parse_llm_response(
        raw_response=sample_response,
        target_module="testbed.app.services.order_service",
        technique=PromptTechnique.CHAIN_OF_THOUGHT,
    )

    assert suite.target_module == "testbed.app.services.order_service"
    assert len(suite.test_cases) == 1
    assert suite.test_cases[0].test_name == "test_discount_boundary"
    assert suite.test_cases[0].target_function == "calculate_discount"
