"""
Safety Guardrails Subsystem for TestPilot AI.
Provides input prompt sanitization, AST-level generated code safety analysis,
and Spec-as-Oracle conformance verification against hallucinations.
"""

from testpilot.guardrails.engine import (
    SafetyGuardrailEngine,
    check_spec_adherence,
    inspect_input_prompt,
    sanitize_input_prompt,
    validate_generated_code,
)
from testpilot.guardrails.rules import (
    ALLOWED_IMPORT_MODULES,
    DANGEROUS_CALLS,
    PROMPT_INJECTION_PATTERNS,
    GuardrailCheckResult,
    GuardrailViolationError,
    GuardrailViolationType,
)

__all__ = [
    "SafetyGuardrailEngine",
    "sanitize_input_prompt",
    "inspect_input_prompt",
    "validate_generated_code",
    "check_spec_adherence",
    "GuardrailCheckResult",
    "GuardrailViolationError",
    "GuardrailViolationType",
    "ALLOWED_IMPORT_MODULES",
    "DANGEROUS_CALLS",
    "PROMPT_INJECTION_PATTERNS",
]
