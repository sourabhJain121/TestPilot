from src.testpilot.engine.prompt_manager import GeneratedTestCase, TestSuiteModel

def test_prompt_model_validation():
    tc = GeneratedTestCase(
        test_name="test_checkout_max_discount",
        category="boundary",
        reasoning="Verifies discount cannot exceed 100",
        code="def test_checkout_max_discount(): assert True"
    )
    suite = TestSuiteModel(test_cases=[tc])
    assert len(suite.test_cases) == 1
    assert suite.test_cases[0].test_name == "test_checkout_max_discount"
