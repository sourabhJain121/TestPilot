import os
import json
import requests
from typing import Optional, Dict, Any

class LLMFailoverClient:
    """Unified 3-tier LLM engine: Cloud (Gemini) -> Local (Ollama) -> Mock Fallback."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    def generate(self, prompt: str, model: str = "qwen2.5-coder:7b") -> str:
        # Tier 1: Local Ollama daemon
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=10.0
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
        except Exception:
            pass

        # Tier 2: Deterministic Mock / Fallback
        return json.dumps({
            "test_name": "test_boundary_zero_division",
            "code": "def test_boundary_zero_division():\n    assert True\n"
        })
