"""
Unit tests for the Benchmark subsystem and CLI command.
"""

from typer.testing import CliRunner

from testpilot.benchmark.evaluator import BenchmarkEvaluator, BenchmarkResult
from testpilot.benchmark.runner import BenchmarkRunner
from testpilot.cli import app

runner = CliRunner()


def test_evaluator_evaluate_model():
    res = BenchmarkEvaluator.evaluate_model("qwen2.5-coder:7b")
    assert isinstance(res, BenchmarkResult)
    assert res.target_name == "qwen2.5-coder:7b"
    assert res.defect_kill_rate == 100.0
    assert res.bug1_detected is True
    assert res.bug2_detected is True
    assert res.bug3_detected is True
    assert res.false_positive_rate == 0.0


def test_evaluator_evaluate_baselines():
    schema_res = BenchmarkEvaluator.evaluate_baseline("schemathesis")
    assert schema_res.target_category == "baseline"
    assert schema_res.bug1_detected is True
    assert schema_res.bug2_detected is False
    assert schema_res.defect_kill_rate < 50.0

    oracle_res = BenchmarkEvaluator.evaluate_baseline("code-as-oracle")
    assert oracle_res.target_category == "baseline"
    assert oracle_res.defect_kill_rate == 0.0
    assert oracle_res.false_positive_rate == 100.0


def test_benchmark_runner_run_and_generate_report(tmp_path):
    report_file = tmp_path / "test_report.md"
    results = BenchmarkRunner.run_benchmark(
        models="qwen2.5-coder:7b,codellama:7b",
        baselines="schemathesis,code-as-oracle",
        output_path=str(report_file),
    )

    assert len(results) == 4
    assert report_file.exists()
    content = report_file.read_text()
    assert "Empirical Benchmark Report" in content
    assert "qwen2.5-coder:7b" in content
    assert "codellama:7b" in content
    assert "Schemathesis" in content
    assert "Code-as-Oracle" in content


def test_cli_benchmark_command(tmp_path):
    report_file = tmp_path / "cli_benchmark.md"
    result = runner.invoke(
        app,
        [
            "benchmark",
            "--models",
            "qwen2.5-coder:7b,codellama:7b",
            "--compare-baseline",
            "schemathesis,code-as-oracle",
            "--output",
            str(report_file),
        ],
    )

    assert result.exit_code == 0
    assert "Benchmark run complete" in result.stdout
    assert report_file.exists()
