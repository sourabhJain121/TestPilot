"""
Unit tests for TestPilot AI CLI commands (analyze, generate-boundaries, generate-tests).
"""

from pathlib import Path
from typer.testing import CliRunner
from testpilot.cli import app

runner = CliRunner()


def test_cli_analyze_default():
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 0
    assert "Repository & Contract Analysis Complete" in result.stdout
    assert "OpenAPI Constraints" in result.stdout
    assert "AST Symbols Extracted" in result.stdout


def test_cli_analyze_custom_options(tmp_path):
    # Test specifying custom repo-path, openapi, and prd
    result = runner.invoke(
        app,
        [
            "analyze",
            "--repo-path", "testbed/",
            "--openapi", "testbed/openapi.json",
            "--prd", "docs/PRD.md",
        ],
    )
    assert result.exit_code == 0
    assert "Repository & Specification Intelligence Engine" in result.stdout
    assert "testbed" in result.stdout


def test_cli_generate_boundaries_command(tmp_path):
    output_dir = tmp_path / "out_boundaries"
    result = runner.invoke(
        app,
        [
            "generate-boundaries",
            "--openapi", "testbed/openapi.json",
            "--output-dir", str(output_dir),
        ],
    )
    assert result.exit_code == 0
    expected_file = output_dir / "test_deterministic_boundaries.py"
    assert expected_file.exists()
    assert expected_file.stat().st_size > 0
    assert "test_order_totals_minimum" in expected_file.read_text()


def test_cli_generate_tests_options(tmp_path):
    output_dir = tmp_path / "out_tests"
    result = runner.invoke(
        app,
        [
            "generate-tests",
            "--file", "testbed/app/services/order_service.py",
            "--openapi", "testbed/openapi.json",
            "--output-dir", str(output_dir),
            "--technique", "cot",
        ],
    )
    assert result.exit_code == 0
    expected_file = output_dir / "test_order_service.py"
    assert expected_file.exists()
    assert expected_file.stat().st_size > 0


def test_cli_parse_diff_default():
    result = runner.invoke(app, ["parse-diff"])
    assert result.exit_code == 0
    assert "Discovered Functions" in result.stdout
    assert "calculate_order" in result.stdout


def test_cli_check_sourcegraph_default():
    result = runner.invoke(app, ["check-sourcegraph"])
    assert result.exit_code == 0
    assert "Tracing caller hierarchy for symbol: calculate_order_totals" in result.stdout
    assert "Callers of 'calculate_order_totals'" in result.stdout

