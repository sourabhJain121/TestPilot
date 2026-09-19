import requests
from typing import List, Dict, Any, Optional

class SourcegraphClient:
    """Queries Sourcegraph GraphQL API for cross-repository symbol navigation."""

    def __init__(self, endpoint: str = "http://localhost:7080", token: Optional[str] = None):
        self.endpoint = f"{endpoint}/.api/graphql"
        self.headers = {"Authorization": f"token {token}"} if token else {}

    def find_references(self, symbol_name: str, repo: str) -> List[Dict[str, Any]]:
        query = """
        query SearchSymbols($query: String!) {
          search(query: $query, version: V1) {
            results {
              results {
                ... on FileMatch {
                  file { path }
                  lineMatches { lineNumber preview }
                }
              }
            }
          }
        }
        """
        search_query = f"repo:{repo} type:symbol {symbol_name}"
        try:
            resp = requests.post(
                self.endpoint,
                json={"query": query, "variables": {"query": search_query}},
                headers=self.headers,
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("search", {}).get("results", {}).get("results", [])
        except Exception:
            return []
        return []
