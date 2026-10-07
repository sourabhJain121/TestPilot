"""
Unit tests for Sourcegraph client and Local AST Fallback.
"""

from testpilot.sourcegraph.client import LocalCodeGraphFallback, SourcegraphClient


def test_sourcegraph_client_fallback_mode():
    client = SourcegraphClient(endpoint="http://localhost:9999/.api/graphql", timeout=0.1)
    # When Sourcegraph is offline, is_available and is_alive return False gracefully
    assert client.is_available() is False
    assert client.is_alive() is False


def test_local_fallback_finds_callers_of_order_service():
    fallback = LocalCodeGraphFallback(repo_root=".")
    callers = fallback.find_callers("calculate_order_totals")

    # In testbed/app/main.py, create_order calls OrderService.calculate_order_totals
    assert len(callers) >= 1
    caller_names = [c["caller_name"] for c in callers]
    file_paths = [c["file_path"] for c in callers]

    assert "create_order" in caller_names
    assert any("testbed/app/main.py" in p for p in file_paths)


def test_local_fallback_finds_status_transition_callers():
    fallback = LocalCodeGraphFallback(repo_root=".")
    callers = fallback.find_callers("transition_order_status")

    assert len(callers) >= 1
    caller_names = [c["caller_name"] for c in callers]
    assert "transition_order_status" in caller_names


def test_sourcegraph_definitions_and_references():
    client = SourcegraphClient(repo_root=".")
    defs = client.find_definitions("calculate_order_totals")
    assert isinstance(defs, list)
    assert len(defs) >= 1
    assert any("order_service.py" in d["file_path"] for d in defs)

    refs = client.find_references("calculate_order_totals")
    assert isinstance(refs, list)
    assert len(refs) >= 1


def test_sourcegraph_test_references():
    client = SourcegraphClient(repo_root=".")
    test_refs = client.find_test_references("calculate_order_totals")
    assert isinstance(test_refs, list)
    # References should be from test files
    for r in test_refs:
        assert "test" in r["file_path"].lower()


def test_sourcegraph_class_usages():
    client = SourcegraphClient(repo_root=".")
    usages = client.find_class_usages("OrderService")
    assert isinstance(usages, list)
    assert len(usages) >= 1


def test_sourcegraph_normalize_evidence():
    client = SourcegraphClient(repo_root=".")
    # In offline fallback mode:
    ev = client.normalize_evidence(
        query="type:references calculate_order_totals",
        symbol="calculate_order_totals",
        results=[{"caller_name": "create_order", "file_path": "testbed/app/main.py", "source_type": "local_ast_fallback"}],
    )
    assert ev["symbol"] == "calculate_order_totals"
    assert ev["has_evidence"] is True
    assert ev["availability"] == "UNAVAILABLE"
    assert ev["status"] == "SOURCEGRAPH_UNAVAILABLE_FALLBACK"
    assert ev["results_count"] == 1


def test_sourcegraph_mocked_online_flow(monkeypatch):
    client = SourcegraphClient()
    monkeypatch.setattr(client, "is_available", lambda: True)

    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "data": {
                    "search": {
                        "results": {
                            "results": [
                                {
                                    "file": {"path": "testbed/app/routers/orders.py"},
                                    "symbols": [
                                        {
                                            "name": "calculate_order_totals",
                                            "kind": "FUNCTION",
                                            "location": {"range": {"start": {"line": 42}}},
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            }

    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockResponse())

    defs = client.find_definitions("calculate_order_totals")
    assert len(defs) == 1
    assert defs[0]["source_type"] == "sourcegraph_graphql"
    assert defs[0]["line_number"] == 42
