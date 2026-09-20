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
