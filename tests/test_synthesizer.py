"""
Unit tests for PytestSynthesizer and AST syntax validation.
"""

import ast

from testpilot.core.models import GeneratedTestCase, GeneratedTestSuite, PromptTechnique
from testpilot.generator.synthesizer import PytestSynthesizer


def test_synthesizer_creates_valid_ast_code(tmp_path):
    output_file = tmp_path / "test_synth.py"
    suite = GeneratedTestSuite(
        target_module="testbed.app.services.order_service",
        technique_used=PromptTechnique.CHAIN_OF_THOUGHT,
        test_cases=[
            GeneratedTestCase(
                test_name="test_calculate_tax_precision",
                target_function="calculate_tax",
                boundary_focus="Fractional cent rounding",
                input_values={"taxable_amount": 10.06},
                expected_behavior="Tax equals 0.83",
                rationale="Round up 0.82995 to 0.83",
            )
        ],
        reasoning_trace="CoT boundary trace",
    )

    code = PytestSynthesizer.synthesize_suite(suite, output_path=str(output_file))
    assert output_file.exists()
    assert "def test_calculate_tax_precision():" in code

    # Verify python ast syntax
    parsed = ast.parse(code)
    assert isinstance(parsed, ast.Module)
