"""
Rule definitions, violation categories, and schemas for the TestPilot Safety Guardrails.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GuardrailViolationError(ValueError):
    """Raised when an input or output violates safety guardrail policies."""
    pass


# Disallowed dangerous module or function calls
DANGEROUS_CALLS = {
    "os.system",
    "os.popen",
    "os.spawn",
    "os.remove",
    "os.unlink",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.run",
    "subprocess.check_output",
    "shutil.rmtree",
    "sys.exit",
    "socket.socket",
    "eval",
    "exec",
    "__import__",
    "Path.unlink",
    "unlink",
}

# Permitted import packages for generated test code
ALLOWED_IMPORT_MODULES = {
    "pytest",
    "unittest",
    "math",
    "decimal",
    "datetime",
    "pydantic",
    "testbed",
    "testbed.app",
    "testbed.app.models",
    "testbed.app.services",
    "testbed.app.services.order_service",
    "typing",
    "dataclasses",
    "uuid",
    "enum",
    "json",
    "re",
}

# Prompt injection regex patterns to detect and neutralize
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\b(?:ignore|disregard|override|forget)\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|rules|prompts|directives)\b",
    r"(?i)\b(?:system\s+override|jailbreak|developer\s+mode|dan\s+mode)\b",
    r"(?i)\b(?:delete|drop|truncate|purge)\s+(?:all\s+)?(?:database|table|files|schema)\b",
    r"(?i)\b(?:rm\s+-rf|format\s+c:|del\s+/f|sudo\s+rm)\b",
    r"(?i)\b(?:steal|exfiltrate|leak)\s+(?:api\s+key|token|password|credentials|secret)\b",
]

# Maximum safe token/character length for prompts
MAX_SAFE_PROMPT_LENGTH = 8192


class GuardrailViolationType(str, Enum):
    PROMPT_INJECTION = "PROMPT_INJECTION"
    PROMPT_LENGTH_EXCEEDED = "PROMPT_LENGTH_EXCEEDED"
    DANGEROUS_IMPORT = "DANGEROUS_IMPORT"
    DANGEROUS_CALL = "DANGEROUS_CALL"
    UNAUTHORIZED_IMPORT = "UNAUTHORIZED_IMPORT"
    UNAUTHORIZED_FILE_WRITE = "UNAUTHORIZED_FILE_WRITE"
    NETWORK_EXFILTRATION = "NETWORK_EXFILTRATION"
    GUARDRAIL_REJECTED_HALLUCINATION = "GUARDRAIL_REJECTED_HALLUCINATION"


class GuardrailCheckResult(BaseModel):
    is_valid: bool = Field(..., description="Whether the analyzed artifact complies with all safety rules.")
    violations: list[str] = Field(default_factory=list, description="List of detected safety violations.")
    violation_types: list[GuardrailViolationType] = Field(default_factory=list, description="Categorized violation types.")
    safety_score: float = Field(default=1.0, description="Normalized safety score: 1.0 (safe) to 0.0 (high risk).")
    details: dict[str, Any] = Field(default_factory=dict, description="Metadata and sub-check breakdowns.")
