from unittest.mock import MagicMock, patch

from testpilot.core.pipeline import FullPipelineOrchestrator, PipelineRunRequest
from testpilot.evolution.models import (
    EvidenceTrail,
    EvolutionReport,
    PrioritizedTest,
    PriorityTier,
)
from testpilot.rag.semantic_validator import SemanticDecision, SemanticValidationResult


def _mock_evolution_report():
    test1 = PrioritizedTest(
        test_name="test_checkout_calculate_total",
        test_file="tests/test_checkout.py",
        priority_tier=PriorityTier.HIGH,
        priority_score=0.9,
        reason="Direct AST caller",
        targeted_symbol="calculate_total",
        evidence=EvidenceTrail(
            call_chain=["test_checkout_calculate_total", "calculate_total"],
            caller_file="tests/test_checkout.py",
            match_quality="EXACT_AST_CALL",
            resolution_engine="AST",
        ),
    )
    test2 = PrioritizedTest(
        test_name="test_unrelated_logger",
        test_file="tests/test_logger.py",
        priority_tier=PriorityTier.LOW,
        priority_score=0.3,
        reason="Co-changed file heuristic",
        targeted_symbol="calculate_total",
        evidence=EvidenceTrail(
            call_chain=["test_unrelated_logger"],
            caller_file="tests/test_logger.py",
            match_quality="HEURISTIC",
            resolution_engine="AST",
        ),
    )
    return EvolutionReport(
        base_ref="HEAD~1",
        target_ref="HEAD",
        diff_stat="1 file changed",
        changed_files=["core/pricing.py"],
        changed_symbols=[],
        prioritized_tests=[test1, test2],
    )


def test_pipeline_semantic_validation_disabled_by_default(tmp_path):
    orchestrator = FullPipelineOrchestrator()
    req = PipelineRunRequest(
        repo_path=str(tmp_path),
        enable_semantic_validation=False,
    )
    assert req.enable_semantic_validation is False

    with patch("subprocess.run") as mock_run, \
         patch("testpilot.core.pipeline.RepositoryEvolutionEngine") as mock_engine_cls:
        # Mock git status
        mock_run.return_value = MagicMock(returncode=0)
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = _mock_evolution_report()
        mock_engine_cls.return_value = mock_engine

        result = orchestrator._run_evolution_stage(req)

        assert result.status == "SUCCESS"
        assert result.semantic_validation_enabled is False
        assert len(result.semantic_validation_results) == 0
        assert len(result.prioritized_tests) == 2


def test_pipeline_semantic_validation_enabled(tmp_path):
    orchestrator = FullPipelineOrchestrator()
    req = PipelineRunRequest(
        repo_path=str(tmp_path),
        enable_semantic_validation=True,
    )

    with patch("subprocess.run") as mock_run, \
         patch("testpilot.core.pipeline.RepositoryEvolutionEngine") as mock_engine_cls, \
         patch("testpilot.rag.semantic_validator.SemanticTestValidator") as mock_val_cls, \
         patch("testpilot.rag.repo_vector_store.RepoCodeVectorStore") as mock_store_cls:

        mock_run.return_value = MagicMock(returncode=0)
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = _mock_evolution_report()
        mock_engine_cls.return_value = mock_engine

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        mock_validator = MagicMock()
        # High for test 1, Low for test 2
        def fake_validate(candidate_test_name, **kwargs):
            if "checkout" in candidate_test_name:
                return SemanticValidationResult(
                    decision=SemanticDecision.HIGH,
                    behaviorally_relevant=True,
                    confidence=0.95,
                    reason="Direct checkout unit test",
                    supporting_evidence=["Direct call"],
                )
            else:
                return SemanticValidationResult(
                    decision=SemanticDecision.LOW,
                    behaviorally_relevant=False,
                    confidence=0.8,
                    reason="Irrelevant logging test",
                    supporting_evidence=[],
                )

        mock_validator.validate_candidate.side_effect = fake_validate
        mock_val_cls.return_value = mock_validator

        result = orchestrator._run_evolution_stage(req)

        assert result.status == "SUCCESS"
        assert result.semantic_validation_enabled is True
        assert len(result.semantic_validation_results) == 2
        # test1 is HIGH and preserved. test2 is LOW and filtered from final execution list
        assert len(result.prioritized_tests) == 1
        assert result.prioritized_tests[0].test_name == "test_checkout_calculate_total"
        assert result.prioritized_tests[0].semantic_decision == "HIGH"


def test_pipeline_semantic_validation_graceful_fallback_on_error(tmp_path):
    orchestrator = FullPipelineOrchestrator()
    req = PipelineRunRequest(
        repo_path=str(tmp_path),
        enable_semantic_validation=True,
    )

    with patch("subprocess.run") as mock_run, \
         patch("testpilot.core.pipeline.RepositoryEvolutionEngine") as mock_engine_cls, \
         patch("testpilot.rag.semantic_validator.SemanticTestValidator") as mock_val_cls:

        mock_run.return_value = MagicMock(returncode=0)
        mock_engine = MagicMock()
        mock_engine.analyze.return_value = _mock_evolution_report()
        mock_engine_cls.return_value = mock_engine

        # Validator raises unexpected exception
        mock_val_cls.side_effect = RuntimeError("Ollama connection refused")

        result = orchestrator._run_evolution_stage(req)

        # Baseline tests are preserved safely
        assert result.status == "SUCCESS"
        assert len(result.prioritized_tests) == 2
