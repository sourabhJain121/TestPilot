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
        if (
            os.getenv("TESTPILOT_CI_MODE", "").lower() in ("true", "1", "yes")
            or os.getenv("TESTPILOT_OFFLINE_MODE", "").lower() in ("true", "1", "yes")
            or os.getenv("MOCK_LLM", "").lower() in ("true", "1", "yes")
        ):
            return {
                "connected": True,
                "model_requested": self.model,
                "model_available": True,
                "installed_models": [self.model],
                "ci_mode": True,
            }

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

    def _generate_ci_offline_fixture(self, prompt: str, json_format: bool = False) -> str:
        """Deterministic offline responses for headless CI environments."""
        import json
        p_lower = prompt.lower()

        # 1. Three-Valued Arbitration Responses
        if "test name:" in p_lower or "three-valued" in p_lower or "verdict" in p_lower:
            import re
            match = re.search(r"test name:\s*(\S+)", prompt, re.IGNORECASE)
            t_name = match.group(1).lower() if match else ""

            if "ambig" in t_name or "underspec" in t_name or "empty_cart" in t_name:
                return json.dumps({
                    "verdict": "SPEC_AMBIGUITY_OR_DEFECT",
                    "spec_clause": "Specification silent or ambiguous on boundary condition",
                    "explanation": "The specification is ambiguous, contradictory, or silent regarding the expected behavior for this boundary condition.",
                    "confidence_score": 0.92,
                    "recommended_fix": "Clarify boundary condition rules in OpenAPI / PRD specification contract before asserting behavior.",
                })
            elif "hallucinated" in t_name or "unknown_coupon" in t_name or "discount coupon" in p_lower:
                return json.dumps({
                    "verdict": "INVALID_TEST_ASSERTION",
                    "spec_clause": "PRD section 3.1: Only valid coupons SAVE10, SAVE20, FLAT50, WELCOME5 are recognized.",
                    "explanation": "Test asserted an ungrounded expectation not defined in the specification.",
                    "confidence_score": 0.95,
                    "recommended_fix": "Update or remove hallucinated test assertion to match formal specification.",
                })
            elif "tax" in t_name or "rounding" in t_name or "0.82" in p_lower or "precision" in t_name:
                return json.dumps({
                    "verdict": "TRUE_CODE_DEFECT",
                    "spec_clause": "PRD Sec 4.2: Half-up rounding on 8.25% sales tax calculation",
                    "explanation": "OrderService.calculate_tax truncated fractional cents instead of standard decimal round-half-up.",
                    "confidence_score": 0.96,
                    "recommended_fix": "Replace int(taxable * rate * 100) / 100.0 with round(taxable * rate, 2).",
                })
            elif "transition" in t_name or "status" in t_name or "jump" in t_name or "cancelled" in t_name:
                return json.dumps({
                    "verdict": "TRUE_CODE_DEFECT",
                    "spec_clause": "State Machine Specification: CANCELLED and COMPLETED are terminal states",
                    "explanation": "OrderService erroneously allowed CANCELLED order to transition directly to COMPLETED.",
                    "confidence_score": 0.99,
                    "recommended_fix": "Remove if requested == OrderStatus.COMPLETED: return True exception from CANCELLED state handler.",
                })
            else:
                return json.dumps({
                    "verdict": "TRUE_CODE_DEFECT",
                    "spec_clause": "PRD section 3.2: Discount amount must not exceed subtotal, ensuring non-negative order total.",
                    "explanation": "OrderService.calculate_order_totals produced a negative total when fixed coupon exceeded subtotal.",
                    "confidence_score": 0.98,
                    "recommended_fix": "Clamp fixed discount calculation to subtotal before computing total: min(subtotal, rule['value']).",
                })

        # 2. Test Generation Structured Suite (CoT / PromptManager)
        if json_format or "test_cases" in p_lower or "cot" in p_lower:
            return json.dumps({
                "target_module": "testbed.app.services.order_service",
                "technique_used": "cot",
                "reasoning_trace": "Offline CI deterministic fixture grounded in domain specs.",
                "test_cases": [
                    {
                        "test_name": "test_free_shipping_threshold_boundary",
                        "target_function": "calculate_order_totals",
                        "boundary_focus": "Free shipping boundary threshold ($50.00)",
                        "input_values": {"subtotal_below": 40.0, "subtotal_above": 50.0},
                        "expected_behavior": "shipping is 5.99 when subtotal < 50.0; shipping is 0.0 when subtotal >= 50.0",
                        "rationale": "Threshold boundary analysis for shipping charges.",
                    }
                ],
            })

        # 3. Patch / Remediation Source Code Generation
        if "original source code" in p_lower or "corrected python code" in p_lower:
            return """```python
# Remediation patch applied in CI mode
def calculate_discount(coupon_code, subtotal):
    if not coupon_code:
        return 0.0
    return min(subtotal, 50.0)
```"""

        return "Deterministic offline fixture response."

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_format: bool = False,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate completion from the local Ollama model or deterministic CI fixture.
        """
        if (
            os.getenv("TESTPILOT_CI_MODE", "").lower() in ("true", "1", "yes")
            or os.getenv("TESTPILOT_OFFLINE_MODE", "").lower() in ("true", "1", "yes")
            or os.getenv("MOCK_LLM", "").lower() in ("true", "1", "yes")
        ):
            return self._generate_ci_offline_fixture(prompt, json_format=json_format)

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

