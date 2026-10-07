"""
Focused test suite for Repository Evolution Intelligence integration into the Full Pipeline.
Validates:
1. Full pipeline invokes Evolution analysis.
2. Evolution results are included in the full pipeline response.
3. Prioritized tests are propagated into the pipeline.
4. Evolution failure gracefully degrades without crashing.
5. Zero impacted tests does not break the pipeline (no fabrication).
6. Sourcegraph unavailable still works with local AST fallback.
7. Standalone /api/evolution/analyze still works independently.
8. Existing full pipeline behavior still works.
9. Web UI renders Evolution results.
10. Full pipeline still completes successfully without Evolution data.
11. CLI testpilot pipeline command.
"""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from testpilot.cli import app as cli_app
from testpilot.core.pipeline import FullPipelineOrchestrator, PipelineRunRequest
from testpilot.evolution import PriorityTier
from testpilot.web.api import app

client = TestClient(app)
cli_runner = CliRunner()


def test_full_pipeline_invokes_evolution_analysis():
    """Verify that calling full pipeline executes Stage 0 Evolution Intelligence."""
    response = client.post("/api/pipeline/run", json={
        "repo_path": ".",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "enable_evolution": True,
    })
    assert response.status_code == 200
    data = response.json()

    assert "evolution" in data
    evo = data["evolution"]
    assert evo["status"] in ("SUCCESS", "DEGRADED")
    assert "changed_files" in evo
    assert "changed_symbols" in evo
    assert "direct_impacts" in evo
    assert "indirect_impacts" in evo
    assert "blast_radius_size" in evo
    assert "prioritized_tests" in evo
    assert "analysis_latency_ms" in evo
    assert isinstance(evo["executable_commands"], list)


def test_evolution_results_included_in_full_pipeline_response():
    """Verify the full pipeline response contains all 10 required component results."""
    response = client.post("/api/pipeline/run", json={
        "repo_path": ".",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "enable_evolution": True,
    })
    assert response.status_code == 200
    data = response.json()

    # 1. Evolution analysis summary
    assert "evolution" in data
    assert "status" in data["evolution"]

    # 2. Impacted symbols
    assert "total_impacted_symbols" in data["evolution"]
    assert "direct_impacts" in data["evolution"]
    assert "indirect_impacts" in data["evolution"]

    # 3. Blast-radius summary
    assert "blast_radius_size" in data["evolution"]

    # 4. Prioritized regression tests
    assert "prioritized_tests" in data["evolution"]

    # 5. Existing boundary-test results
    assert "boundary_testing" in data
    assert data["boundary_testing"]["total_boundaries"] >= 0

    # 6. 3-valued arbitration results
    assert "arbitration" in data
    assert data["arbitration"]["total_arbitrated"] > 0
    verdicts = [item["verdict"] for item in data["arbitration"]["breakdown"]]
    assert "TRUE_CODE_DEFECT" in verdicts

    # 7. Safety guardrail results
    assert "guardrails" in data
    assert "safety_score" in data["guardrails"]
    assert data["guardrails"]["is_valid"] is True

    # 8. Remediation result
    assert "remediation" in data
    assert data["remediation"]["patch_generated"] is True

    # 9. Sandbox verification result
    assert "sandbox_verification" in data
    assert data["sandbox_verification"]["verified_in_sandbox"] is True

    # 10. Overall pipeline status
    assert "overall_status" in data
    assert data["overall_status"] in ("SUCCESS", "COMPLETED_WITH_WARNINGS")


def test_prioritized_tests_propagated_into_pipeline():
    """Verify prioritized tests preserve tier, score, commands, and influence regression execution."""
    orchestrator = FullPipelineOrchestrator()
    req = PipelineRunRequest(
        repo_path=".",
        base_ref="HEAD~1",
        target_ref="HEAD",
        enable_evolution=True,
    )
    result = orchestrator.execute(req)

    assert result.evolution is not None
    assert isinstance(result.evolution.prioritized_tests, list)

    # Verify that regression stage captures prioritized test count and executable commands
    reg = result.regression_testing
    assert reg.status == "SUCCESS"
    assert len(reg.commands_executed) > 0

    # If prioritized tests exist, verify priority tiers and scores are preserved
    for t in result.evolution.prioritized_tests:
        assert t.priority_tier in (PriorityTier.CRITICAL, PriorityTier.HIGH, PriorityTier.MEDIUM, PriorityTier.LOW)
        assert 0.0 <= t.priority_score <= 1.0
        assert t.execution_command.startswith("pytest ")
        assert t.test_name is not None
        assert t.test_file is not None


def test_evolution_failure_gracefully_degrades():
    """Verify that an invalid Git ref degrades gracefully without crashing the pipeline."""
    response = client.post("/api/pipeline/run", json={
        "repo_path": ".",
        "base_ref": "non_existent_ref_xyz_99999",
        "target_ref": "HEAD",
        "enable_evolution": True,
    })
    assert response.status_code == 200
    data = response.json()

    # Evolution marked degraded
    assert data["evolution"]["status"] == "DEGRADED"
    assert data["evolution"]["warning"] is not None
    assert "Git reference" in data["evolution"]["warning"] or "non_existent_ref" in data["evolution"]["warning"]

    # Pipeline completed with warnings, not crashed
    assert data["overall_status"] == "COMPLETED_WITH_WARNINGS"

    # Core downstream stages still ran successfully
    assert data["boundary_testing"]["status"] in ("SUCCESS", "SKIPPED")
    assert data["arbitration"]["total_arbitrated"] > 0
    assert data["guardrails"]["is_valid"] is True
    assert data["remediation"]["patch_generated"] is True
    assert data["sandbox_verification"]["verified_in_sandbox"] is True


def test_zero_impacted_tests_does_not_break_pipeline():
    """Verify comparing HEAD to HEAD (0 diff) yields 0 impacts and does not fabricate tests."""
    response = client.post("/api/pipeline/run", json={
        "repo_path": ".",
        "base_ref": "HEAD",
        "target_ref": "HEAD",
        "enable_evolution": True,
    })
    assert response.status_code == 200
    data = response.json()

    # Zero changes detected
    assert data["evolution"]["status"] == "SUCCESS"
    assert len(data["evolution"]["changed_files"]) == 0
    assert len(data["evolution"]["changed_symbols"]) == 0
    assert data["evolution"]["blast_radius_size"] == 0
    assert len(data["evolution"]["prioritized_tests"]) == 0

    # Pipeline completed without crashing
    assert data["overall_status"] == "SUCCESS"
    assert data["boundary_testing"]["total_boundaries"] == 49


def test_sourcegraph_unavailable_uses_local_ast_fallback():
    """Verify local AST fallback is used when Sourcegraph is offline."""
    with patch("testpilot.sourcegraph.client.SourcegraphClient.is_alive", return_value=False):
        response = client.post("/api/pipeline/run", json={
            "repo_path": ".",
            "base_ref": "HEAD~1",
            "target_ref": "HEAD",
            "enable_evolution": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["evolution"]["status"] in ("SUCCESS", "DEGRADED")
        assert data["overall_status"] in ("SUCCESS", "COMPLETED_WITH_WARNINGS")


def test_standalone_evolution_analyze_endpoint_intact():
    """Verify standalone POST /api/evolution/analyze remains functional independently."""
    response = client.post("/api/evolution/analyze", json={
        "repo_path": ".",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "max_depth": 3,
    })
    assert response.status_code == 200
    data = response.json()
    assert "changed_files" in data
    assert "changed_symbols" in data
    assert "direct_impacts" in data
    assert "indirect_impacts" in data
    assert "prioritized_tests" in data


def test_existing_full_pipeline_behavior_still_works():
    """Verify running pipeline with enable_evolution=False preserves existing workflow."""
    response = client.post("/api/pipeline/run", json={
        "enable_evolution": False,
        "spec_path": "testbed/openapi.json",
    })
    assert response.status_code == 200
    data = response.json()

    assert data["evolution"]["status"] == "SKIPPED"
    assert data["boundary_testing"]["status"] == "SUCCESS"
    assert data["boundary_testing"]["total_boundaries"] == 49
    assert data["arbitration"]["total_arbitrated"] >= 5
    assert data["guardrails"]["is_valid"] is True
    assert data["remediation"]["patch_generated"] is True
    assert data["sandbox_verification"]["verified_in_sandbox"] is True
    assert data["overall_status"] == "SUCCESS"


def test_web_ui_renders_evolution_results():
    """Verify HTML UI contains dedicated Stage 0 Evolution section and metrics elements."""
    html_file = Path("testpilot/web/static/index.html")
    assert html_file.exists()
    content = html_file.read_text(encoding="utf-8")

    # Dedicated Stage 0 / Evolution Elements
    assert 'id="pipeline-results-section"' in content
    assert 'id="pipeline-evolution-card"' in content
    assert 'id="pipeline-evo-status"' in content
    assert 'id="pipeline-evo-latency"' in content
    assert 'id="pipeline-evo-files"' in content
    assert 'id="pipeline-evo-symbols"' in content
    assert 'id="pipeline-evo-direct"' in content
    assert 'id="pipeline-evo-indirect"' in content
    assert 'id="pipeline-evo-radius"' in content
    assert 'id="pipeline-evo-tests"' in content
    assert 'id="pipeline-evo-critical"' in content
    assert 'id="pipeline-evo-high"' in content
    assert 'id="pipeline-evo-medium"' in content
    assert 'id="pipeline-evo-candidates"' in content
    assert 'id="pipeline-prioritized-tests-container"' in content

    # Pipeline API integration
    assert "/api/pipeline/run" in content
    assert "renderPipelineResults" in content
    assert "downloadPipelineReport" in content

    # Standalone Evolution tab preserved
    assert 'id="tab-evolution"' in content
    assert 'id="tab-btn-evolution"' in content


def test_full_pipeline_completes_without_evolution_data():
    """Verify that when repo_path does not exist, pipeline degrades and finishes successfully."""
    response = client.post("/api/pipeline/run", json={
        "repo_path": "/tmp/non_existent_repo_dir_12345",
        "enable_evolution": True,
    })
    assert response.status_code == 200
    data = response.json()

    assert data["evolution"]["status"] == "DEGRADED"
    assert "does not exist" in (data["evolution"]["warning"] or "")
    assert data["overall_status"] == "COMPLETED_WITH_WARNINGS"
    assert data["boundary_testing"]["total_boundaries"] == 49
    assert data["arbitration"]["total_arbitrated"] > 0


def test_cli_pipeline_command():
    """Verify CLI testpilot pipeline command executes and displays structured tables."""
    result = cli_runner.invoke(cli_app, ["pipeline", "--base", "HEAD", "--target", "HEAD"])
    assert result.exit_code == 0
    assert "Full Autonomous Pipeline Run" in result.output
    assert "0. Repository Evolution" in result.output
    assert "1. OpenAPI Schema Boundaries" in result.output
    assert "2. Regression Test Execution" in result.output
    assert "3. Three-Valued Arbitration" in result.output
    assert "4. Safety Guardrails" in result.output
    assert "5. Remediation & Sandbox" in result.output
