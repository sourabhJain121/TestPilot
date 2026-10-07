import json
from unittest.mock import MagicMock

from testpilot.evolution.models import EvidenceTrail
from testpilot.rag.semantic_validator import (
    SemanticDecision,
    SemanticTestValidator,
)


def test_parse_response_valid_high():
    validator = SemanticTestValidator()
    raw = json.dumps({
        "decision": "HIGH",
        "behaviorally_relevant": True,
        "confidence": 0.95,
        "reason": "Direct unit test for the changed calculation logic.",
        "supporting_evidence": ["Asserts output of calculate_discount", "Calls target function"],
    })
    result = validator._parse_response(raw)
    assert result.decision == SemanticDecision.HIGH
    assert result.behaviorally_relevant is True
    assert result.confidence == 0.95
    assert "Direct unit test" in result.reason
    assert len(result.supporting_evidence) == 2


def test_parse_response_markdown_json_block():
    validator = SemanticTestValidator()
    raw = """
    Here is my evaluation:
    ```json
    {
      "decision": "LOW",
      "behaviorally_relevant": false,
      "confidence": 0.85,
      "reason": "Only touches logging and does not execute the changed business logic.",
      "supporting_evidence": ["No assertion on calculated values"]
    }
    ```
    """
    result = validator._parse_response(raw)
    assert result.decision == SemanticDecision.LOW
    assert result.behaviorally_relevant is False
    assert result.confidence == 0.85
    assert len(result.supporting_evidence) == 1


def test_parse_response_malformed_json_fallback():
    validator = SemanticTestValidator()
    raw = "Not a json response at all! Error or truncated text..."
    result = validator._parse_response(raw, default_relevant=True)
    assert result.decision in (SemanticDecision.MEDIUM, SemanticDecision.LOW)
    assert result.confidence == 0.5
    assert "Parsed with fallback heuristic" in result.reason


def test_critical_recall_protection_preserves_deterministic_candidate(monkeypatch):
    monkeypatch.delenv("TESTPILOT_CI_MODE", raising=False)
    monkeypatch.delenv("TESTPILOT_OFFLINE_MODE", raising=False)
    monkeypatch.delenv("MOCK_LLM", raising=False)

    mock_llm = MagicMock()
    # LLM returns LOW
    mock_llm.generate.return_value = json.dumps({
        "decision": "LOW",
        "behaviorally_relevant": False,
        "confidence": 0.9,
        "reason": "Model claims no relationship exists.",
        "supporting_evidence": [],
    })

    validator = SemanticTestValidator(ollama_client=mock_llm)

    # When is_confirmed_deterministic=True, the candidate must NOT be dropped
    result = validator.validate_candidate(
        candidate_test_name="test_checkout_flow",
        candidate_test_file="tests/test_checkout.py",
        changed_symbol="calculate_total",
        changed_file="core/pricing.py",
        git_diff_snippet="+ def calculate_total(): pass",
        evidence_trail=EvidenceTrail(
            call_chain=["test_checkout_flow", "calculate_total"],
            caller_file="tests/test_checkout.py",
            match_quality="EXACT_AST_CALL",
            resolution_engine="AST",
        ),
        is_confirmed_deterministic=True,
    )

    assert result.decision == SemanticDecision.MEDIUM
    assert result.behaviorally_relevant is True
    assert "Preserved by TestPilot Critical Recall Protection" in result.reason


def test_offline_mode_classification(monkeypatch):
    monkeypatch.setenv("TESTPILOT_OFFLINE_MODE", "1")

    validator = SemanticTestValidator()

    # Direct name match -> HIGH
    res_high = validator.validate_candidate(
        candidate_test_name="test_calculate_total_discount",
        candidate_test_file="tests/test_pricing.py",
        changed_symbol="calculate_total",
        changed_file="core/pricing.py",
        is_confirmed_deterministic=False,
    )
    assert res_high.decision == SemanticDecision.HIGH
    assert res_high.behaviorally_relevant is True

    # Same component/stem -> MEDIUM
    res_medium = validator.validate_candidate(
        candidate_test_name="test_pricing_integration",
        candidate_test_file="tests/test_integration.py",
        changed_symbol="unrelated_helper",
        changed_file="core/pricing.py",
        is_confirmed_deterministic=False,
    )
    assert res_medium.decision == SemanticDecision.MEDIUM
    assert res_medium.behaviorally_relevant is True

    # Unrelated -> LOW when not confirmed deterministic
    res_low = validator.validate_candidate(
        candidate_test_name="test_user_avatar_upload",
        candidate_test_file="tests/test_media.py",
        changed_symbol="calculate_tax",
        changed_file="core/billing.py",
        is_confirmed_deterministic=False,
    )
    assert res_low.decision == SemanticDecision.LOW
    assert res_low.behaviorally_relevant is False
