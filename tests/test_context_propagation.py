"""Tests for Active Analysis Context propagation across TestPilot pipeline stages."""

import pytest
from fastapi.testclient import TestClient

from testpilot.core.context import AnalysisContextManager
from testpilot.web.api import app, context_mgr


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_context():
    context_mgr.reset_active_context()
    yield
    context_mgr.reset_active_context()


def test_context_manager_initial_state():
    mgr = AnalysisContextManager()
    ctx = mgr.get_active_context()
    assert ctx.analysis_id.startswith("run-")
    assert ctx.repo_path == "."
    assert "Testbed" in ctx.repo_name
    assert ctx.completed_stages == []
    assert ctx.current_stage == "evolution"


def test_context_manager_establish_from_evolution():
    mgr = AnalysisContextManager()
    report_data = {
        "repo_path": "/Users/sourabh/testpilot-external-test/flask",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "changed_symbols": [
            {
                "name": "request_context",
                "file_path": "src/flask/app.py",
                "line_start": 300,
                "line_end": 320,
                "change_type": "modified",
            }
        ],
        "changed_files": ["src/flask/app.py"],
        "direct_impacts": [],
        "indirect_impacts": [],
        "prioritized_tests": [],
    }

    ctx = mgr.establish_from_evolution(
        report_data=report_data,
        repo_path="/Users/sourabh/testpilot-external-test/flask",
        base_ref="HEAD~1",
        target_ref="HEAD",
    )

    assert ctx.repo_name == "Flask"
    assert ctx.repo_path == "/Users/sourabh/testpilot-external-test/flask"
    assert ctx.primary_target_file == "src/flask/app.py"
    assert ctx.primary_target_symbol == "request_context"
    assert ctx.spec_available is False
    assert "Not available" in ctx.spec_status
    assert "evolution" in ctx.completed_stages
    assert ctx.current_stage == "ast"


def test_context_manager_spec_detection_testbed():
    mgr = AnalysisContextManager()
    report_data = {
        "repo_path": ".",
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "changed_symbols": [
            {
                "name": "calculate_order_totals",
                "file_path": "testbed/app/services/order_service.py",
                "line_start": 50,
                "line_end": 75,
                "change_type": "modified",
            }
        ],
        "changed_files": ["testbed/app/services/order_service.py"],
        "direct_impacts": [],
        "indirect_impacts": [],
        "prioritized_tests": [],
    }

    ctx = mgr.establish_from_evolution(
        report_data=report_data,
        repo_path=".",
        base_ref="HEAD~1",
        target_ref="HEAD",
    )

    assert "Testbed" in ctx.repo_name
    assert ctx.spec_available is True
    assert "Available" in ctx.spec_status
    assert "testbed/app/schemas/openapi.json" in str(ctx.spec_path) or "openapi.json" in str(ctx.spec_path)


def test_api_context_endpoints(test_client):
    # GET context
    resp = test_client.get("/api/analysis/context")
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis_id" in data
    assert data["analysis_id"].startswith("run-")
    first_id = data["analysis_id"]

    # Update context
    up_resp = test_client.post(
        "/api/analysis/context",
        json={
            "repo_name": "custom_repo",
            "repo_path": "/tmp/custom",
            "primary_target_file": "custom/app.py",
            "primary_target_symbol": "process_event",
        },
    )
    assert up_resp.status_code == 200
    up_data = up_resp.json()
    assert up_data["repo_name"] == "custom_repo"
    assert up_data["primary_target_file"] == "custom/app.py"
    assert up_data["primary_target_symbol"] == "process_event"

    # Reset context
    rst_resp = test_client.post("/api/analysis/reset")
    assert rst_resp.status_code == 200
    rst_data = rst_resp.json()
    assert "Testbed" in rst_data["repo_name"]
    assert rst_data["analysis_id"] != first_id


def test_api_ast_consumes_active_context(test_client):
    # Set context to testbed order_service.py
    test_client.post(
        "/api/analysis/context",
        json={
            "repo_path": ".",
            "repo_name": "Testbed",
            "primary_target_file": "testbed/app/services/order_service.py",
            "primary_target_symbol": "calculate_order_totals",
        },
    )

    # Call /api/ast/parse-diff without explicit file_path
    resp = test_client.post("/api/ast/parse-diff", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["file_path"] == "testbed/app/services/order_service.py"
    assert "Testbed" in data["repo_name"]
    assert data["analysis_id"].startswith("run-")


def test_api_deterministic_honest_spec(test_client):
    # Set context without OpenAPI (simulate Flask)
    test_client.post(
        "/api/analysis/context",
        json={
            "repo_path": ".",
            "repo_name": "Flask",
            "primary_target_file": "testbed/app/services/order_service.py",
            "spec_available": False,
            "spec_status": "Not available",
            "spec_path": None,
        },
    )

    resp = test_client.post("/api/testgen/deterministic", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["spec_available"] is False
    assert data["repo_name"] == "Flask"
    assert "AST Source Code Boundaries" in data["evidence_source"]
    assert data["total_boundaries"] > 0
    assert len(data["sample_cases"]) > 0


def test_evolution_establishes_and_propagates_external_flask(test_client):
    import os

    flask_path = "/Users/sourabh/testpilot-external-test/flask"
    if not os.path.isdir(flask_path):
        pytest.skip("External Flask repo not present")

    # 1. Trigger evolution analysis for Flask
    evo_resp = test_client.post(
        "/api/evolution/analyze",
        json={
            "repo_path": flask_path,
            "base_ref": "HEAD~1",
            "target_ref": "HEAD",
            "max_depth": 2,
        },
    )
    assert evo_resp.status_code == 200
    evo_data = evo_resp.json()
    assert evo_data["repo_name"] == "Flask"
    assert "src/flask/app.py" in evo_data["changed_files"]
    assert evo_data["primary_target_file"] == "src/flask/app.py"
    assert evo_data["spec_available"] is False
    assert "Not available" in evo_data["spec_status"]
    analysis_id = evo_data["analysis_id"]

    # 2. Check context state via /api/analysis/context
    ctx_resp = test_client.get("/api/analysis/context")
    assert ctx_resp.status_code == 200
    ctx_data = ctx_resp.json()
    assert ctx_data["analysis_id"] == analysis_id
    assert ctx_data["repo_name"] == "Flask"
    assert ctx_data["primary_target_file"] == "src/flask/app.py"
    assert ctx_data["spec_available"] is False

    # 3. Call AST parse without hardcoded path -> consumes Flask primary target file
    ast_resp = test_client.post("/api/ast/parse-diff", json={})
    assert ast_resp.status_code == 200
    ast_data = ast_resp.json()
    assert ast_data["file_path"] == "src/flask/app.py"
    assert ast_data["repo_name"] == "Flask"
    assert ast_data["total_functions"] > 0

    # 4. Call Deterministic matrix -> honest spec fallback to AST decision bounds
    det_resp = test_client.post("/api/testgen/deterministic", json={})
    assert det_resp.status_code == 200
    det_data = det_resp.json()
    assert det_data["spec_available"] is False
    assert det_data["repo_name"] == "Flask"
    assert "AST Source Code Boundaries" in det_data["evidence_source"]
    assert det_data["total_boundaries"] > 0

    # 5. Call Caller resolution for Flask symbol
    blast_resp = test_client.get("/api/code-intel/callers?symbol=request_context")
    assert blast_resp.status_code == 200
    blast_data = blast_resp.json()
    assert blast_data["repo_name"] == "Flask"
    assert blast_data["symbol"] == "request_context"

    # 6. Call verify -> handles Flask safely
    verify_resp = test_client.post("/api/verify", json={})
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["repo_name"] == "Flask"


def test_pipeline_run_propagates_context(test_client):
    # Run full pipeline endpoint on testbed
    resp = test_client.post(
        "/api/pipeline/run",
        json={
            "repo_path": ".",
            "base_ref": "HEAD~1",
            "target_ref": "HEAD",
            "enable_evolution": True,
            "enable_semantic_validation": False,
            "enable_sourcegraph": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "analysis_id" in data
    assert data["analysis_id"].startswith("run-")
    assert "Testbed" in data["repo_name"]
    assert data["target_file"] is not None
    assert len(data["target_file"]) > 0
