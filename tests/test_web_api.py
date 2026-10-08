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


def test_api_zero_clone_testgen():
    """Verify in-memory zero-clone test case synthesis from public GitHub repos."""
    res = client.post("/api/repo/zero-clone-testgen", json={
        "repo_url": "https://github.com/pallets/flask/blob/main/src/flask/app.py"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["zero_clone"] is True
    assert data["repo"] == "flask"
    assert data["total_extracted_functions"] >= 10
    assert "def test_" in data["generated_test_suite"]


def test_api_zero_clone_testgen_with_query_params():
    """Verify in-memory zero-clone test case synthesis handles URLs with query parameters and non-main default branches."""
    res = client.post("/api/repo/zero-clone-testgen", json={
        "repo_url": "home-assistant/core?utm_source=chatgpt.com"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["zero_clone"] is True
    assert data["owner"] == "home-assistant"
    assert data["repo"] == "core"
    assert data["branch"] in ("dev", "master")
    assert "homeassistant" in data["resolved_file"]
    assert data["total_extracted_functions"] >= 5
    assert "def test_" in data["generated_test_suite"]


def test_api_report_export_blast_radius():
    """Verify POST /api/report/export handles blast radius report generation."""
    res = client.post("/api/report/export", json={
        "repo_name": "TestPilot",
        "report_type": "blast_radius",
        "data": {
            "symbol": "calculate_order_totals",
            "total_callers": 2,
            "callers": [{"caller_name": "checkout_order", "blast_tier": "CRITICAL"}]
        },
        "markdown_content": "# Blast Radius Report\n\nTarget: calculate_order_totals"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SAVED"
    assert data["success"] is True
    assert "blast_radius" in data["json_file"]


def test_api_sourcegraph_search():
    client = TestClient(app)
    res = client.get("/api/sourcegraph/search?query=calculate_total&search_type=references")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "calculate_total"
    assert "server_status" in data
    assert "normalized_evidence" in data
    assert isinstance(data["results"], list)


def test_api_rag_query():
    client = TestClient(app)
    res = client.post("/api/rag/query", json={"query": "order total test", "top_k": 2})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "order total test"
    assert "total_results" in data
    assert isinstance(data["results"], list)


def test_api_evaluation_overview_endpoint():
    """Verify GET /api/evaluation/overview returns truthful research matrices."""
    client = TestClient(app)
    res = client.get("/api/evaluation/overview")
    assert res.status_code == 200
    data = res.json()

    assert "primary_matrix" in data
    assert len(data["primary_matrix"]) == 6

    # Verify evaluated vs pending distinction
    configs = {row["configuration"]: row for row in data["primary_matrix"]}
    assert configs["Full Regression"]["status"] == "Evaluated"
    assert configs["Naive Baseline"]["status"] == "Evaluated"
    assert configs["TestPilot"]["status"] == "Evaluated"

    assert configs["TestPilot + Sourcegraph"]["status"] == "Not Evaluated / Pending"
    assert configs["TestPilot + Sourcegraph"]["precision"] is None
    assert configs["TestPilot + Sourcegraph"]["precision_display"] == "—"

    assert configs["TestPilot + Repository RAG"]["status"] == "Evaluated"
    assert configs["TestPilot + Repository RAG"]["precision"] == 0.3333
    assert configs["TestPilot + Repository RAG"]["f1_display"] == "46.15%"

    assert configs["TestPilot + Sourcegraph + Repository RAG"]["status"] == "Not Evaluated / Pending"
    assert configs["TestPilot + Sourcegraph + Repository RAG"]["test_reduction_display"] == "—"

    # Status cards
    assert "status_cards" in data
    assert len(data["status_cards"]) == 5

    # Ablation plan
    assert "ablation_plan" in data
    assert len(data["ablation_plan"]) == 6

    # Methodology & Evidence
    assert "methodology" in data
    assert "research_evidence" in data
    assert data["research_evidence"]["rag_evaluated"] is True


def test_api_evaluation_page_html_renders():
    """Verify that root index.html serves the new evaluation matrices and structure."""
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert "Primary Research Evaluation Matrix" in html
    assert "Evaluation &amp; Ablation Plan" in html or "Evaluation & Ablation Plan" in html
    assert "Research Evaluation Status" in html
    assert "Experiment Status Legend" in html
    assert "Evaluation Methodology &amp; Metric Definitions" in html or "Evaluation Methodology & Metric Definitions" in html
    assert "CURRENT RESEARCH EVIDENCE" in html
    assert "eval-status-cards-grid" in html
    assert "eval-primary-matrix-body" in html
    assert "eval-ablation-plan-body" in html



