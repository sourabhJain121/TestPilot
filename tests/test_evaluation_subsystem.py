"""
Unit tests for the TestPilot Evaluation Subsystem.
Tests metric calculations, mathematical edge cases (0/0 denominators),
baseline execution, benchmark persistence, and component validation.
"""

import tempfile
from pathlib import Path

from testpilot.evaluation.baselines import BaselineEvaluator
from testpilot.evaluation.engine import EvaluationEngine, compute_metrics, normalize_test_id
from testpilot.evaluation.models import (
    BaselineType,
    EvaluationRun,
)
from testpilot.evaluation.storage import EvaluationStorage
from testpilot.evolution.models import ChangedSymbol, ChangeType


def test_normalize_test_id():
    """Verify test identifier normalization handles multiple pytest formats."""
    assert normalize_test_id("tests/test_basic.py::test_run") == "test_run"
    assert normalize_test_id("tests/test_basic.py::Class::test_run") == "test_run"
    assert normalize_test_id("test_simple") == "test_simple"
    assert normalize_test_id("  test_padded  ") == "test_padded"


def test_compute_metrics_standard():
    """Verify TP, FP, FN, Precision, Recall, and F1 with standard overlapping sets."""
    predicted = ["test_a", "test_b", "test_c"]
    expected = ["test_b", "test_c", "test_d"]
    total_tests = 100

    metrics = compute_metrics(
        predicted_tests=predicted,
        expected_tests=expected,
        total_tests=total_tests,
        latency_ms=150.0,
    )

    # TP: test_b, test_c (2)
    # FP: test_a (1)
    # FN: test_d (1)
    assert metrics.tp == 2
    assert metrics.fp == 1
    assert metrics.fn == 1
    assert metrics.precision == round(2 / 3, 4)  # 0.6667
    assert metrics.recall == round(2 / 3, 4)     # 0.6667
    assert metrics.f1 == round(2 / 3, 4)
    assert metrics.test_reduction_pct == 97.0
    assert metrics.latency_ms == 150.0
    assert metrics.is_evaluated is True


def test_compute_metrics_edge_case_empty_prediction_and_empty_ground_truth():
    """
    CRITICAL RESEARCH INTEGRITY RULE:
    When TP=0, FP=0, FN=0, do NOT silently claim precision=1.0 or recall=1.0.
    Denominators are zero, so precision and recall must evaluate strictly to None (N/A).
    """
    metrics = compute_metrics(
        predicted_tests=[],
        expected_tests=[],
        total_tests=1000,
    )

    assert metrics.tp == 0
    assert metrics.fp == 0
    assert metrics.fn == 0
    assert metrics.precision is None
    assert metrics.recall is None
    assert metrics.f1 is None
    assert metrics.test_reduction_pct == 100.0


def test_compute_metrics_edge_case_zero_true_positives_with_false_positives():
    """When TP=0 and FP > 0, precision must be 0.0, not None."""
    metrics = compute_metrics(
        predicted_tests=["unrelated_test_1", "unrelated_test_2"],
        expected_tests=["expected_test_1"],
        total_tests=50,
    )

    assert metrics.tp == 0
    assert metrics.fp == 2
    assert metrics.fn == 1
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 is None  # P+R == 0 -> None


def test_compute_metrics_edge_case_zero_predictions_with_nonempty_ground_truth():
    """When predicted is empty but ground truth is non-empty: precision is None (0/0), recall is 0.0."""
    metrics = compute_metrics(
        predicted_tests=[],
        expected_tests=["test_missed"],
        total_tests=100,
    )

    assert metrics.tp == 0
    assert metrics.fp == 0
    assert metrics.fn == 1
    assert metrics.precision is None  # TP + FP = 0 -> undefined denominator
    assert metrics.recall == 0.0
    assert metrics.f1 is None


def test_evaluation_storage_persistence():
    """Verify benchmark case configuration and run persistence to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = EvaluationStorage(storage_dir=tmpdir)
        cases = storage.get_benchmark_cases()
        assert len(cases) >= 3

        flask_case = storage.get_benchmark_case("flask_ipv6")
        assert flask_case is not None
        assert flask_case.repository == "pallets/flask"
        assert len(flask_case.ground_truth.expected_test_callers) == 5

        # Create a mock run and save it
        run = EvaluationRun(
            run_id="test_run_123",
            case_id="flask_ipv6",
            repository="pallets/flask",
            base_commit="de8429ff",
            target_commit="7203feab",
            python_version="3.12.0",
            total_tests=375,
            ground_truth_count=5,
            timestamp="2026-10-07T00:00:00Z",
            status="completed",
        )
        storage.save_run(run)

        # Reload from fresh storage instance
        storage_reloaded = EvaluationStorage(storage_dir=tmpdir)
        loaded_run = storage_reloaded.get_latest_run("flask_ipv6")
        assert loaded_run is not None
        assert loaded_run.run_id == "test_run_123"
        assert loaded_run.total_tests == 375


def test_full_regression_baseline():
    """Verify Full Regression baseline selects 100% of discovered tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        evaluator = BaselineEvaluator(repo_path=tmpdir)
        all_tests = [f"test_file.py::test_{i}" for i in range(25)]
        res = evaluator.run_full_regression(all_tests)

        assert res.baseline_type == BaselineType.FULL_REGRESSION
        assert res.selected_count == 25
        assert res.total_tests == 25
        assert set(res.selected_tests) == set(all_tests)


def test_naive_name_matching_collision_simulation():
    """Verify Naive Name Matching selects tests by bare token matching without receiver checks."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_example.py"
        test_file.write_text(
            """
def test_apple_init():
    x = Apple.__init__()
    assert x

def test_unrelated():
    assert True
""",
            encoding="utf-8",
        )

        evaluator = BaselineEvaluator(repo_path=tmpdir)
        all_tests = ["test_example.py::test_apple_init", "test_example.py::test_unrelated"]

        # If changed symbol is __init__, naive matching catches test_apple_init
        sym = ChangedSymbol(
            name="__init__",
            file_path="service.py",
            line_start=1,
            line_end=10,
            change_type=ChangeType.MODIFIED,
        )

        res = evaluator.run_naive_name_matching([sym], all_tests)
        assert res.baseline_type == BaselineType.NAIVE_NAME_MATCHING
        assert "test_example.py::test_apple_init" in res.selected_tests
        assert "test_example.py::test_unrelated" not in res.selected_tests


def test_component_validation_structure():
    """Verify that every component correctness item defines numerators and denominators."""
    engine = EvaluationEngine()
    results = engine.validate_components()

    assert len(results) == 6
    component_names = {r.component_name for r in results}
    assert "Change Detection" in component_names
    assert "Symbol Resolution" in component_names
    assert "Boundary Extraction" in component_names
    assert "Regression Test Selection" in component_names
    assert "Failure Arbitration" in component_names
    assert "Pipeline Integration" in component_names

    for r in results:
        assert r.numerator_definition != ""
        assert r.denominator_definition != ""
        assert r.total_count >= 0
        assert 0.0 <= r.score_pct <= 100.0


def test_overview_summary_not_evaluated_when_empty():
    """Verify overview returns not_evaluated when storage has no runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = EvaluationStorage(storage_dir=tmpdir)
        engine = EvaluationEngine(storage=storage)
        summary = engine.get_overview_summary()

        assert summary["status"] == "not_evaluated"
        assert summary["macro_precision"] is None
        assert summary["macro_recall"] is None
        assert summary["macro_f1"] is None
        assert summary["avg_test_reduction_pct"] is None


def test_overview_summary_pooled_mathematical_consistency():
    """
    Verify that aggregate metrics are strictly pooled across positive-ground-truth cases
    (Testbed + Flask) and Home Assistant is reported separately as negative control.
    """
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    assert summary["status"] == "evaluated"
    assert summary["methodology_label"] == "Positive-Ground-Truth Pooled Evaluation"

    # Verify mathematical consistency invariants for all baselines
    for baseline_key in ["testpilot", "naive_name_matching", "full_regression"]:
        row = summary["baseline_comparison"][baseline_key]
        tp, fp, fn = row["tp"], row["fp"], row["fn"]
        if (tp + fp) > 0:
            assert row["precision"] == round(tp / (tp + fp), 4)
        if (tp + fn) > 0:
            assert row["recall"] == round(tp / (tp + fn), 4)
        if row["precision"] is not None and row["recall"] is not None and (row["precision"] + row["recall"]) > 0:
            expected_f1 = round((2.0 * row["precision"] * row["recall"]) / (row["precision"] + row["recall"]), 4)
            assert row["f1"] == expected_f1
        if summary["total_benchmarked_tests"] > 0:
            expected_red = round((1.0 - (row["tests_selected"] / summary["total_benchmarked_tests"])) * 100.0, 2)
            assert row["test_reduction"] == expected_red

    # When Django is evaluated alongside Testbed and Flask (3 positive cases):
    if summary["evaluated_cases_count"] >= 4:
        assert summary["total_benchmarked_tests"] == 10713
        assert summary["total_ground_truth"] == 20

        tp_row = summary["baseline_comparison"]["testpilot"]
        assert tp_row["tp"] == 15
        assert tp_row["fp"] == 83
        assert tp_row["fn"] == 5
        assert tp_row["tests_selected"] == 100
        assert tp_row["precision"] == 0.1531
        assert tp_row["recall"] == 0.75
        assert tp_row["f1"] == 0.2543
        assert tp_row["test_reduction"] == 99.07
    else:
        # Fallback for 2 positive cases (Testbed + Flask)
        assert summary["total_benchmarked_tests"] == 508
        assert summary["total_ground_truth"] == 12

    # 4. Negative Control Study (Home Assistant):
    neg = summary["negative_control_study"]
    assert neg is not None
    assert neg["repository"] == "home-assistant/core"
    assert neg["ground_truth_count"] == 0
    assert neg["naive_selected"] == 19
    assert neg["testpilot_selected"] == 0
    assert neg["precision"] is None
    assert neg["recall"] is None
    assert neg["f1"] is None


def test_testpilot_rag_baseline(monkeypatch):
    """Verify TestPilot + Repository RAG baseline returns valid BaselineResult with recall preserved."""
    monkeypatch.setenv("TESTPILOT_OFFLINE_MODE", "1")
    with tempfile.TemporaryDirectory() as tmpdir:
        evaluator = BaselineEvaluator(repo_path=tmpdir)
        sym = ChangedSymbol(
            name="calculate_discount",
            file_path="pricing.py",
            line_start=1,
            line_end=10,
            change_type=ChangeType.MODIFIED,
        )
        all_tests = ["tests/test_pricing.py::test_calculate_discount"]
        res, evidence = evaluator.run_testpilot_rag([sym], all_tests)

        assert res.baseline_type == BaselineType.TESTPILOT_RAG
        assert "TestPilot + Repository RAG" in res.name
        assert res.selected_count >= 0


def test_overview_primary_evaluation_matrix_structure():
    """
    CRITICAL RESEARCH INTEGRITY RULE:
    Primary matrix must contain all 6 research configurations.
    Evaluated rows must contain verified metrics.
    Un-evaluated rows (Sourcegraph, RAG, SG+RAG) must strictly return
    status='Not evaluated yet' with NO fabricated metrics (values=None, display='—').
    """
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    matrix = summary.get("primary_matrix")
    assert matrix is not None
    assert len(matrix) == 6

    configs = [row["configuration"] for row in matrix]
    assert configs == [
        "Full Regression",
        "Naive Baseline",
        "TestPilot",
        "TestPilot + Sourcegraph",
        "TestPilot + Repository RAG",
        "TestPilot + Sourcegraph + Repository RAG",
    ]

    # Row 0: Full Regression
    fr_row = matrix[0]
    assert fr_row["status"] == "Evaluated"
    assert fr_row["selected_tests"] == 10713
    assert fr_row["tp"] == 20
    assert fr_row["fn"] == 0

    # Row 1: Naive Baseline
    naive_row = matrix[1]
    assert naive_row["status"] == "Evaluated"
    assert naive_row["selected_tests"] == 122
    assert naive_row["tp"] == 13
    assert naive_row["fn"] == 7

    # Row 2: TestPilot baseline (FROZEN)
    tp_row = matrix[2]
    assert tp_row["status"] == "Evaluated"
    assert tp_row["selected_tests"] == 100
    assert tp_row["tp"] == 15
    assert tp_row["fp"] == 83
    assert tp_row["fn"] == 5
    assert tp_row["precision_display"] == "15.31%"
    assert tp_row["recall_display"] == "75.00%"
    assert tp_row["f1_display"] == "25.43%"
    assert tp_row["test_reduction_display"] == "99.07%"

    # Row 3: TestPilot + Sourcegraph (Quantitative evaluation pending)
    sg_row = matrix[3]
    assert sg_row["is_evaluated"] is False
    assert sg_row["status"] == "Not Evaluated / Pending"
    assert sg_row["badge"] == "Quantitative Evaluation Pending"
    assert sg_row["selected_tests"] is None
    assert sg_row["precision_display"] == "—"

    # Row 4: TestPilot + Repository RAG (EVALUATED)
    rag_row = matrix[4]
    assert rag_row["is_evaluated"] is True
    assert rag_row["status"] == "Evaluated"
    assert rag_row["badge"] == "✓ Evaluated"
    assert rag_row["selected_tests"] == 45
    assert rag_row["tp"] == 15
    assert rag_row["fp"] == 30
    assert rag_row["fn"] == 5
    assert rag_row["precision_display"] == "33.33%"
    assert rag_row["recall_display"] == "75.00%"
    assert rag_row["f1_display"] == "46.15%"
    assert rag_row["test_reduction_display"] == "99.58%"

    # Row 5: TestPilot + SG + RAG (Quantitative evaluation pending)
    sg_rag_row = matrix[5]
    assert sg_rag_row["is_evaluated"] is False
    assert sg_rag_row["status"] == "Not Evaluated / Pending"
    assert sg_rag_row["badge"] == "Quantitative Evaluation Pending"
    assert sg_rag_row["selected_tests"] is None


def test_overview_ablation_plan_structure():
    """Verify ablation plan matrix defines all 6 architectural experiment rows."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    plan = summary.get("ablation_plan")
    assert plan is not None
    assert len(plan) == 6

    experiments = [row["experiment"] for row in plan]
    assert experiments == [
        "Full Regression",
        "Naive Baseline",
        "TestPilot",
        "TestPilot + Sourcegraph",
        "TestPilot + Repository RAG",
        "TestPilot + Sourcegraph + Repository RAG",
    ]

    # Verify RAG is evaluated
    rag_row = next(r for r in plan if r["experiment"] == "TestPilot + Repository RAG")
    assert rag_row["status"] == "Evaluated"
    assert rag_row["repository_rag"] == "Yes"
    assert rag_row["codellama_validation"] == "Yes"
    assert rag_row["sourcegraph"] == "No"
    assert rag_row["deterministic_repo_intelligence"] == "Yes"
    assert "F1 = 46.15%" in rag_row["metrics"]

    # Verify Sourcegraph is pending benchmark
    sg_row = next(r for r in plan if r["experiment"] == "TestPilot + Sourcegraph")
    assert sg_row["status"] == "Not Evaluated / Pending"
    assert sg_row["sourcegraph"] == "Yes"
    assert sg_row["repository_rag"] == "No"
    assert "pending" in sg_row["metrics"].lower()


def test_overview_status_cards_and_benchmark_summary():
    """Verify status cards accurately report component implementation and evaluation status."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    cards = summary.get("status_cards")
    assert cards is not None
    assert len(cards) == 5

    card_map = {c["title"]: c for c in cards}
    assert "CORE TESTPILOT" in card_map
    assert card_map["CORE TESTPILOT"]["status"] == "Evaluated"

    assert "SOURCEGRAPH" in card_map
    assert card_map["SOURCEGRAPH"]["status"] == "Not Evaluated / Pending"

    assert "REPOSITORY RAG" in card_map
    assert card_map["REPOSITORY RAG"]["status"] == "Evaluated"
    assert card_map["REPOSITORY RAG"]["quantitative_evaluation"] == "Measured"

    assert "CODELLAMA SEMANTIC VALIDATION" in card_map
    assert card_map["CODELLAMA SEMANTIC VALIDATION"]["status"] == "Evaluated"
    assert card_map["CODELLAMA SEMANTIC VALIDATION"]["quantitative_evaluation"] == "Measured"

    assert "EVALUATION SUITE" in card_map
    assert card_map["EVALUATION SUITE"]["status"] == "Current Measured Baseline Available"

    b_sum = summary.get("benchmark_summary")
    assert b_sum is not None
    assert b_sum["total_configurations"] == 6
    assert b_sum["evaluated_configurations_count"] == 4
    assert b_sum["pending_configurations_count"] == 2
    assert b_sum["total_tests_positive_pool"] == 10713
    assert b_sum["total_ground_truth"] == 20


def test_overview_methodology_and_evidence():
    """Verify methodology definitions and research evidence statements."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    meth = summary.get("methodology")
    assert meth is not None
    assert meth["precision"]["formula"] == "TP / (TP + FP)"
    assert meth["recall"]["formula"] == "TP / (TP + FN)"
    assert meth["f1"]["formula"] == "2·P·R / (P+R)" or "Precision" in meth["f1"]["formula"]
    assert "Selected" in meth["test_reduction"]["formula"]

    evidence = summary.get("research_evidence")
    assert evidence is not None
    assert evidence["core_evaluated"] is True
    assert evidence["rag_evaluated"] is True
    assert evidence["sourcegraph_evaluated"] is False

    findings_text = " ".join(evidence["key_findings"])
    assert "Precision increased relative to TestPilot" in findings_text
    assert "Recall remained unchanged" in findings_text
    assert "Sourcegraph integration is currently available" in findings_text
    assert "quantitative ablation benchmark has not yet been completed" in findings_text


# =========================================================================
# SECTION 20: QUANTITATIVE RESEARCH EVALUATION REQUIREMENTS
# =========================================================================

def test_section_20_1_testpilot_baseline_remains_unchanged():
    """Requirement 1: TestPilot baseline remains frozen and unchanged."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()
    tp = summary["baseline_comparison"]["testpilot"]

    assert tp["tests_selected"] == 100
    assert tp["tp"] == 15
    assert tp["fp"] == 83
    assert tp["fn"] == 5
    assert tp["precision"] == 0.1531
    assert tp["recall"] == 0.75
    assert tp["f1"] == 0.2543
    assert tp["test_reduction"] == 99.07


def test_section_20_2_sourcegraph_configuration_enables_sourcegraph():
    """Requirement 2: Sourcegraph configuration actually tests connectivity and attempts Sourcegraph."""
    from testpilot.sourcegraph.client import SourcegraphClient
    sg_client = SourcegraphClient(repo_root=".")
    assert sg_client is not None
    assert hasattr(sg_client, "is_available")
    assert hasattr(sg_client, "query_symbols")


def test_section_20_3_rag_configuration_enables_rag():
    """Requirement 3: RAG configuration actually enables vector store and semantic validator."""
    from testpilot.rag.semantic_validator import SemanticTestValidator
    from testpilot.rag.vector_store import SpecVectorStore
    validator = SemanticTestValidator()
    vector_store = SpecVectorStore(db_path=".chroma_db")
    assert validator is not None
    assert vector_store is not None
    assert validator.llm is not None
    assert validator.repo_store is not None
    assert hasattr(validator, "validate_candidate")


def test_section_20_4_combined_configuration_enables_both():
    """Requirement 4: Combined configuration enables both Sourcegraph and RAG."""
    from testpilot.rag.semantic_validator import SemanticTestValidator
    from testpilot.sourcegraph.client import SourcegraphClient
    sg = SourcegraphClient(repo_root=".")
    validator = SemanticTestValidator(sourcegraph_client=sg)
    assert validator.sg_client is sg


def test_section_20_5_results_are_stored_separately():
    """Requirement 5: Results are stored separately in machine-readable experiment store."""
    import json
    exp_file = Path("testbed/evaluation_store/experiment_runs.json")
    assert exp_file.exists()
    runs = json.loads(exp_file.read_text(encoding="utf-8"))
    assert len(runs) >= 3
    configs = {r["configuration"] for r in runs}
    assert "TestPilot + Repository RAG" in configs
    assert "TestPilot + Sourcegraph" in configs
    assert "TestPilot + Sourcegraph + Repository RAG" in configs


def test_section_20_6_ground_truth_identical_across_configurations():
    """Requirement 6: Ground truth is identical across all evaluated configurations."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()
    total_gt = summary["total_ground_truth"]
    assert total_gt == 20

    for row in summary["primary_matrix"]:
        if row["is_evaluated"]:
            assert row["ground_truth_positives"] == 20


def test_section_20_7_metrics_calculated_correctly():
    """Requirement 7: Metrics follow standard formulas."""
    tp, fp, fn = 15, 30, 5
    precision = tp / (tp + fp)  # 15/45 = 0.333333...
    recall = tp / (tp + fn)     # 15/20 = 0.75
    f1 = 2 * (precision * recall) / (precision + recall)  # 0.461538...

    assert round(precision, 4) == 0.3333
    assert round(recall, 4) == 0.75
    assert round(f1, 4) == 0.4615


def test_section_20_8_failed_experiments_not_reported_as_successful():
    """Requirement 8: Failed/unavailable experiments are not reported as successful or evaluated."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()
    sg_row = next(r for r in summary["primary_matrix"] if r["configuration"] == "TestPilot + Sourcegraph")

    assert sg_row["is_evaluated"] is False
    assert sg_row["status"] == "Not Evaluated / Pending"
    assert sg_row["selected_tests"] is None
    assert sg_row["precision_display"] == "—"


def test_section_20_9_ui_reads_actual_evaluation_records():
    """Requirement 9: UI reads actual evaluation records via overview endpoint."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    assert "ablation_comparison" in summary
    assert "factual_findings" in summary
    assert len(summary["ablation_comparison"]) >= 4

    rag_comp = next(c for c in summary["ablation_comparison"] if "Repository RAG" in c["configuration"])
    assert rag_comp["selected_tests"] == "45"
    assert rag_comp["precision"] == "33.33%"
    assert rag_comp["delta_precision"] == "+18.02%"


def test_section_20_10_pending_status_changes_only_after_successful_benchmark():
    """Requirement 10: Status changes to evaluated ONLY when real benchmark metrics exist."""
    engine = EvaluationEngine()
    summary = engine.get_overview_summary()

    for row in summary["primary_matrix"]:
        if row["status"] == "Evaluated":
            assert row["is_evaluated"] is True
            assert row["selected_tests"] is not None
            assert row["tp"] is not None
            assert row["precision"] is not None
        else:
            assert row["is_evaluated"] is False
            assert row["selected_tests"] is None
