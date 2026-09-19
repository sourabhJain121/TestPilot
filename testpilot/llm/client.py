"""
Unified LLM Client for TestPilot AI.
Interfaces with local Ollama daemon (http://localhost:11434) running code models
such as qwen2.5-coder:7b or deepseek-coder:6.7b.
"""

import os
from typing import Any, Optional

import requests


class OllamaLLMClient:
    """
    HTTP client for querying local Ollama instances with JSON schema formatting,
    model discovery, and error recovery.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        timeout: float = 120.0,
    ):
        self.base_url = os.getenv("OLLAMA_BASE_URL", base_url).rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", model)
        self.timeout = timeout

    def check_health(self) -> dict[str, Any]:
        """Verify Ollama service is reachable and return installed models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                model_ready = any(self.model in m for m in models)
                return {
                    "connected": True,
                    "model_requested": self.model,
                    "model_available": model_ready,
                    "installed_models": models,
                }
            return {
                "connected": False,
                "error": f"HTTP status {resp.status_code}",
                "model_available": False,
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "model_available": False,
            }

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_format: bool = False,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate completion from the local Ollama model.
        """
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if system_instruction:
            payload["system"] = system_instruction
        if json_format:
            payload["format"] = "json"

        try:
            resp = requests.post(endpoint, json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama generation failed with status {resp.status_code}: {resp.text}")
            result = resp.json()
            return result.get("response", "")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Ollama generation timed out after {self.timeout}s.") from None
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with Ollama: {e}") from e
