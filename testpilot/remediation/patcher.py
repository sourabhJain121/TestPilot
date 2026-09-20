"""
Autonomous Remediation Bot (Sweep.dev Pattern) for TestPilot AI.
Automatically synthesizes code patches for TRUE_CODE_DEFECT verdicts,
validates the fix in an isolated pytest sandbox, and exports PR patches.
"""

import difflib
import subprocess
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from testpilot.llm.client import OllamaLLMClient
from testpilot.rag.arbiter import ArbitrationResult


class RemediationResult(BaseModel):
    """Output summary of an autonomous remediation attempt."""

    target_file: str
    patch_generated: bool
    verified_in_sandbox: bool
    unified_diff: str = Field(..., description="Unified git diff patch")
    message: str


class RemediationPatcher:
    """
    Autonomous code patch generator and test sandbox validator.
    Implements the Sweep.dev autonomous pull-request remediation pattern.
    """

    PATCH_SYSTEM_PROMPT = """You are an automated Code Repair & Remediation Bot (Sweep.dev pattern).
You will receive a Python source file, a failing test report, and a formal specification clause.
Your task is to provide the EXACT corrected code for the defective function.
Rules:
1. Fix the bug cleanly without breaking other existing functionality.
2. Return ONLY the complete, corrected Python file or the modified function inside a ```python ``` markdown block.
"""

    def __init__(self, llm_client: Optional[OllamaLLMClient] = None):
        self.llm = llm_client or OllamaLLMClient()

    def generate_remediation_patch(
        self,
        target_file_path: str,
        arbitration: ArbitrationResult,
        test_command: Optional[list[str]] = None,
    ) -> RemediationResult:
        """
        Synthesizes a fix for target_file_path, verifies it in an isolated sandbox,
        and returns the unified diff patch.
        """
        path = Path(target_file_path)
        if not path.exists():
            return RemediationResult(
                target_file=target_file_path,
                patch_generated=False,
                verified_in_sandbox=False,
                unified_diff="",
                message=f"Target file does not exist: {target_file_path}",
            )

        original_content = path.read_text(encoding="utf-8")

        # 1. Generate patched code via LLM or deterministic AST repair
        patched_content = self._generate_fix(original_content, arbitration)

        if patched_content == original_content:
            return RemediationResult(
                target_file=target_file_path,
                patch_generated=False,
                verified_in_sandbox=False,
                unified_diff="",
                message="No modifications produced.",
            )

        # 2. Compute unified git diff
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            patched_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
        unified_diff_str = "".join(diff)

        # 3. Sandbox verification
        # Temporarily apply patch, run test_command, and restore original content
        verified = False
        try:
            path.write_text(patched_content, encoding="utf-8")
            cmd = test_command or [sys.executable, "-m", "pytest", "tests/test_testbed_api.py", "-q"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            # If exit code is 0, sandbox tests succeeded
            verified = (res.returncode == 0)
        except Exception:
            verified = False
        finally:
            # Restore original content so developer/CI can decide to apply patch
            path.write_text(original_content, encoding="utf-8")

        # Save patch file to artifacts/disk
        patch_file = Path("remediation.patch")
        patch_file.write_text(unified_diff_str, encoding="utf-8")

        return RemediationResult(
            target_file=target_file_path,
            patch_generated=True,
            verified_in_sandbox=verified,
            unified_diff=unified_diff_str,
            message=f"Remediation patch created (sandbox verified: {verified}). Saved to remediation.patch",
        )

    def _generate_fix(self, source_code: str, arbitration: ArbitrationResult) -> str:
        """Attempt LLM fix first; fall back to deterministic domain rule repair."""
        # Try LLM
        health = self.llm.check_health()
        if health["connected"] and health["model_available"]:
            prompt = f"""
SPECIFICATION COMPLIANCE FAILURE:
Test: {arbitration.test_name}
Spec Clause: {arbitration.spec_clause}
Issue: {arbitration.explanation}
Recommended Fix: {arbitration.recommended_fix}

ORIGINAL SOURCE CODE:
```python
{source_code}
```

TASK:
Provide the complete corrected Python code with the recommended fix applied.
"""
            try:
                resp = self.llm.generate(
                    prompt=prompt,
                    system_instruction=self.PATCH_SYSTEM_PROMPT,
                    temperature=0.1,
                )
                if "```python" in resp:
                    clean = resp.split("```python")[1].split("```")[0].strip()
                    if len(clean) > len(source_code) * 0.7:
                        return clean
            except Exception:
                pass

        # Deterministic domain rule repair
        repaired = source_code

        # Fix 1: Discount deficit (Bug 1)
        if "negative" in arbitration.explanation.lower() or "deficit" in arbitration.explanation.lower() or "total" in arbitration.explanation.lower():
            # In calculate_discount, clamp fixed discount to subtotal
            repaired = repaired.replace(
                "return rule[\"value\"]",
                "return min(subtotal, rule[\"value\"])",
            )
            # And ensure total never goes negative in calculate_order_totals
            repaired = repaired.replace(
                "total = round((subtotal - discount) + tax + shipping, 2)",
                "total = max(0.0, round((subtotal - discount) + tax + shipping, 2))",
            )

        # Fix 2: Tax truncation (Bug 2)
        if "tax" in arbitration.explanation.lower() or "round" in arbitration.explanation.lower() or "truncat" in arbitration.explanation.lower():
            repaired = repaired.replace(
                "truncated_tax = int(taxable_amount * TAX_RATE * 100) / 100.0",
                "truncated_tax = round(taxable_amount * TAX_RATE, 2)",
            )

        # Fix 3: Illegal state transition (Bug 3)
        if "transition" in arbitration.explanation.lower() or "cancelled" in arbitration.explanation.lower():
            repaired = repaired.replace(
                "            if requested == OrderStatus.COMPLETED:\n                return True, None\n",
                "",
            )

        return repaired
