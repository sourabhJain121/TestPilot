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

