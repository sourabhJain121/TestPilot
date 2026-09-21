"""
Unit and integration tests for TestPilot AI Web API endpoints.
Tests FastAPI REST routes, static file serving, and core engine integrations.
"""

from fastapi.testclient import TestClient

from testpilot.web.api import app

client = TestClient(app)


def test_serve_index_html():
    """Verify root / serves the developer dashboard HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "TestPilot AI" in response.text
    assert "Spec-as-Oracle" in response.text
    assert "Three-Valued" in response.text or "3-Valued" in response.text


def test_api_status():
    """Verify GET /api/status returns subsystem health diagnostics."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "python_runtime" in data
    assert "ollama" in data
    assert "sourcegraph" in data
    assert "vector_store" in data
    assert data["ollama"]["status"] in ["ONLINE", "OFFLINE"]


def test_api_ast_parse_diff_default():
    """Verify POST /api/ast/parse-diff parses the testbed service functions and boundaries."""
    response = client.post("/api/ast/parse-diff", json={"file_path": "testbed/app/services/order_service.py"})
    assert response.status_code == 200
    data = response.json()
    assert data["total_functions"] >= 3
    names = [f["name"] for f in data["functions"]]
    assert "calculate_order_totals" in names
    assert "calculate_discount" in names
    assert "transition_order_status" in names


def test_api_ast_parse_custom_diff():
    """Verify POST /api/ast/parse-diff with explicit diff string."""
    diff_snippet = """--- a/testbed/app/services/order_service.py
+++ b/testbed/app/services/order_service.py
@@ -10,1 +10,1 @@
-def foo(): pass
+def foo(x: int) -> int:
+    if x < 0:
+        return 0
+    return x
"""
    response = client.post("/api/ast/parse-diff", json={"diff": diff_snippet})
    assert response.status_code == 200
    data = response.json()
    assert data["file_path"] == "unified_diff_patch"


def test_api_code_intel_callers():
    """Verify GET /api/code-intel/callers returns upstream callers."""
    response = client.get("/api/code-intel/callers?symbol=calculate_order_totals")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "calculate_order_totals"
    assert "total_callers" in data
    assert "resolution_engine" in data
    assert isinstance(data["callers"], list)


def test_api_testgen_deterministic():
    """Verify POST /api/testgen/deterministic synthesizes 49 schema-grounded boundary tests."""
    response = client.post("/api/testgen/deterministic", json={
        "spec_path": "testbed/openapi.json",
        "output_path": "tests/generated/test_deterministic_boundaries.py"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_boundaries"] == 49
    assert "constraint_breakdown" in data
    assert "exclusiveMinimum" in data["constraint_breakdown"]
    assert len(data["sample_cases"]) > 0


def test_api_verify():
    """Verify POST /api/verify executes testbed assertions and returns three-valued arbitration."""
    response = client.post("/api/verify", json={
        "test_path": "tests/generated/test_order_service.py"
    })
    assert response.status_code == 200
    data = response.json()
    assert "total_tests" in data
    assert "passed" in data
    assert "failed" in data
    assert "arbitration_breakdown" in data

    verdicts = [r["verdict"] for r in data["arbitration_breakdown"]]
    assert "TRUE_CODE_DEFECT" in verdicts
    assert "INVALID_TEST_ASSERTION" in verdicts
    assert "SPEC_AMBIGUITY_OR_DEFECT" in verdicts


def test_api_benchmark():
    """Verify GET /api/benchmark runs the multi-model and baseline evaluation harness."""
    response = client.get("/api/benchmark?models=qwen2.5-coder:7b&compare_baseline=schemathesis")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "baselines" in data
    assert "results" in data
    assert len(data["results"]) >= 2


def test_api_remediate():
    """Verify POST /api/remediate generates a verified sandbox patch."""
    response = client.post("/api/remediate", json={
        "file_path": "testbed/app/services/order_service.py",
        "output_patch": "remediation.patch"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["patch_generated"] is True
    assert data["verified_in_sandbox"] is True
    assert "---" in data["unified_diff"] or "@@" in data["unified_diff"]


def test_api_guardrails_check():
    """Verify POST /api/guardrails/check evaluates code safety constraints."""
    response = client.post("/api/guardrails/check", json={
        "code_file": "tests/generated/test_order_service.py"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["safety_score"] == 1.0
    assert len(data["violations"]) == 0


def test_api_guardrails_audit():
    """Verify GET /api/guardrails/audit returns audit logs."""
    response = client.get("/api/guardrails/audit")
    assert response.status_code == 200
    data = response.json()
    assert "total_files_audited" in data
    assert data["total_files_audited"] >= 1
    assert "audit_logs" in data
    assert isinstance(data["audit_logs"], list)

