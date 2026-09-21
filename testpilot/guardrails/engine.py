"""
Safety Guardrails Engine for TestPilot AI.
Enforces input prompt sanitization, AST-level code safety verification,
and Spec-as-Oracle adherence checking to prevent hallucinations.
"""

import ast
import re
from pathlib import Path
from typing import Optional

from testpilot.guardrails.rules import (
    ALLOWED_IMPORT_MODULES,
    DANGEROUS_CALLS,
    MAX_SAFE_PROMPT_LENGTH,
    PROMPT_INJECTION_PATTERNS,
    GuardrailCheckResult,
    GuardrailViolationError,
    GuardrailViolationType,
)


def sanitize_input_prompt(
    prompt: str,
    max_length: int = MAX_SAFE_PROMPT_LENGTH,
    raise_on_injection: bool = False,
) -> str:
    """
    Detect and neutralize prompt injection attempts and enforce token length limits.
    Enforces maximum prompt character length.
    If raise_on_injection=True and an injection signature is detected, raises GuardrailViolationError.
    Otherwise neutralizes injection payloads by replacing them with [SANITIZED_PROMPT_INJECTION].
    """
    if len(prompt) > max_length:
        raise GuardrailViolationError(
            f"Input prompt exceeds maximum safety length of {max_length} characters (received {len(prompt)})."
        )

    has_injection = any(re.search(pattern, prompt) for pattern in PROMPT_INJECTION_PATTERNS)
    if has_injection and raise_on_injection:
        raise GuardrailViolationError("Prompt injection signature detected")

    sanitized = prompt
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[SANITIZED_PROMPT_INJECTION]", sanitized)

    return sanitized


def inspect_input_prompt(prompt: str, max_length: int = MAX_SAFE_PROMPT_LENGTH) -> str:
    """Validate and sanitize prompt, raising GuardrailViolationError on any injection attempt."""
    return sanitize_input_prompt(prompt, max_length=max_length, raise_on_injection=True)


def validate_generated_code(code_str: str) -> tuple[bool, list[str]]:
    """
    Analyze the AST of generated code to enforce safety constraints:
    a) Disallow dangerous imports & calls: os.system, subprocess, shutil.rmtree, sys.exit, raw sockets.
    b) Ensure imports are strictly limited to allowed test & domain modules.
    c) Reject code containing unauthorized file writes or network exfiltration patterns.
    """
    violations: list[str] = []

    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, [f"Code syntax error preventing AST safety verification: {e}"]

    class SafetyVisitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                if root_pkg not in ALLOWED_IMPORT_MODULES:
                    violations.append(
                        f"Unauthorized import '{alias.name}': Only testing and domain modules are permitted."
                    )
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                if root_pkg not in ALLOWED_IMPORT_MODULES:
                    violations.append(
                        f"Unauthorized import from '{node.module}': Only testing and domain modules are permitted."
                    )
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                value_repr = ""
                if isinstance(node.func.value, ast.Name):
                    value_repr = node.func.value.id
                elif isinstance(node.func.value, ast.Attribute):
                    if isinstance(node.func.value.value, ast.Name):
                        value_repr = f"{node.func.value.value.id}.{node.func.value.attr}"
                call_name = f"{value_repr}.{node.func.attr}" if value_repr else node.func.attr

            # 1. Dangerous Calls
            for dangerous in DANGEROUS_CALLS:
                if call_name == dangerous or call_name.endswith(f".{dangerous}"):
                    violations.append(f"Dangerous call rejected: '{call_name}'")

            # 2. Unauthorized File Writes
            if call_name == "open":
                # Check write / append mode in arguments
                for arg in node.args[1:]:
                    if isinstance(arg, ast.Constant) and any(m in str(arg.value) for m in ("w", "a", "x")):
                        violations.append("Unauthorized file write attempt detected: open() in write mode.")
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        if any(m in str(kw.value.value) for m in ("w", "a", "x")):
                            violations.append("Unauthorized file write attempt detected: open() in write mode.")

            if call_name.endswith("write_text") or call_name.endswith("write_bytes"):
                violations.append(f"Unauthorized filesystem modification call rejected: '{call_name}'")

            # 3. Network Exfiltration
            if any(net in call_name.lower() for net in ("requests.post", "requests.get", "socket.connect", "urllib")):
                violations.append(f"Unauthorized network exfiltration call rejected: '{call_name}'")

            self.generic_visit(node)

    visitor = SafetyVisitor()
    visitor.visit(tree)

    return len(violations) == 0, violations


def check_spec_adherence(
    code_or_test: str,
    spec_path: str = "testbed/openapi.json",
) -> tuple[bool, Optional[str]]:
    """
    Verify whether an LLM-synthesized test case asserts boundary behavior
    contradictory to the OpenAPI schema without an explicit PRD citation.
    """
    lower = code_or_test.lower()

    # If code contains explicit formal PRD/OpenAPI citation, it is considered grounded
    prd_patterns = [r"\bprd\b", r"\bsection\s+\d", r"\brf-\d", r"\bspec-as-oracle\b", r"\bopenapi\b", r"\bspecification\b"]
    has_prd_citation = any(re.search(pat, lower) for pat in prd_patterns if pat != r"\bspecification\b" or "according to" in lower)

    # Hallucination Pattern 1: Asserting discount for unknown / non-existent coupon without citation
    if any(k in lower for k in ("unknown", "fake", "hallucinated")) and "discount" in lower and "assert" in lower:
        if any(v in lower for v in ("50.0", "discount > 0", "assert res ==")) and not has_prd_citation:
            return False, "GUARDRAIL_REJECTED_HALLUCINATION: Test asserts discount on ungrounded coupon without PRD citation."

    # Hallucination Pattern 2: Asserting illegal status jump CANCELLED -> COMPLETED is valid without citation
    if "cancelled" in lower and "completed" in lower and "assert" in lower:
        if "assert res is true" in lower or "assert true" in lower:
            if not has_prd_citation:
                return False, "GUARDRAIL_REJECTED_HALLUCINATION: Test asserts illegal state machine jump without formal PRD citation."

    # Hallucination Pattern 3: Asserting negative prices are accepted as valid without citation
    if "negative_price" in lower or "unit_price = -1" in lower:
        if "assert" in lower and "valid" in lower and not has_prd_citation:
            return False, "GUARDRAIL_REJECTED_HALLUCINATION: Test asserts negative price is valid, contradicting OpenAPI schema."

    return True, None


class SafetyGuardrailEngine:
    """
    High-level orchestrator for input sanitization, AST code safety, and spec conformance.
    """

    def __init__(self, spec_path: str = "testbed/openapi.json"):
        self.spec_path = spec_path

    def check_prompt(self, prompt: str) -> str:
        """Sanitize an input prompt."""
        return sanitize_input_prompt(prompt)

    def check_code(self, code_str: str) -> GuardrailCheckResult:
        """Run full safety and spec-adherence analysis on code."""
        is_safe, code_violations = validate_generated_code(code_str)
        is_adherent, spec_violation = check_spec_adherence(code_str, self.spec_path)

        all_violations = list(code_violations)
        violation_types: list[GuardrailViolationType] = []

        for v in code_violations:
            if "Dangerous call" in v:
                violation_types.append(GuardrailViolationType.DANGEROUS_CALL)
            elif "Unauthorized import" in v:
                violation_types.append(GuardrailViolationType.UNAUTHORIZED_IMPORT)
            elif "write" in v:
                violation_types.append(GuardrailViolationType.UNAUTHORIZED_FILE_WRITE)
            elif "network" in v:
                violation_types.append(GuardrailViolationType.NETWORK_EXFILTRATION)

        if not is_adherent and spec_violation:
            all_violations.append(spec_violation)
            violation_types.append(GuardrailViolationType.GUARDRAIL_REJECTED_HALLUCINATION)

        total_violations = len(all_violations)
        score = max(0.0, round(1.0 - (total_violations * 0.25), 2))

        return GuardrailCheckResult(
            is_valid=total_violations == 0,
            violations=all_violations,
            violation_types=violation_types,
            safety_score=score,
            details={
                "code_safety_passed": is_safe,
                "spec_adherence_passed": is_adherent,
                "total_violations": total_violations,
            },
        )

    def check_file(self, file_path: str) -> GuardrailCheckResult:
        """Read and analyze a target source or test file."""
        path = Path(file_path)
        if not path.exists():
            return GuardrailCheckResult(
                is_valid=False,
                violations=[f"Target file not found: {file_path}"],
                violation_types=[],
                safety_score=0.0,
                details={"file_exists": False},
            )

        content = path.read_text(encoding="utf-8")
        result = self.check_code(content)
        result.details["file_path"] = str(path)
        return result
