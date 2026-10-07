"""
Data models for the TestPilot Evaluation Engine.
Provides reproducible, traceable schemas for Ground Truth, Baselines,
Evaluated Runs, Metric Calculations, and Component Correctness.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class BaselineType(str, Enum):
    """Supported baseline approaches for regression test selection."""

    FULL_REGRESSION = "full_regression"
    NAIVE_NAME_MATCHING = "naive_name_matching"
    TESTPILOT = "testpilot"


class GroundTruth(BaseModel):
    """
    Independently verified ground truth for a change scenario.
    Ground truth is NEVER generated or inferred by the model itself.
    """

    case_id: str
    expected_changed_symbols: list[str] = Field(
        default_factory=list,
        description="Symbols directly modified in the commit diff",
    )
    expected_impacted_symbols: list[str] = Field(
        default_factory=list,
        description="Downstream functions/methods affected by the change",
    )
    expected_test_callers: list[str] = Field(
        default_factory=list,
        description="Manually verified regression test identifiers exercising the changed behavior",
    )
    provenance: str = Field(
        ...,
        description="Documentation or reference establishing this ground truth independently",
    )
    notes: str = ""
    is_verified: bool = True


class BenchmarkCase(BaseModel):
    """A versioned benchmark scenario targeting a real repository or controlled testbed."""

    case_id: str
    name: str
    repository: str
    repository_path: str
    base_commit: str
    target_commit: str
    description: str
    category: str = Field(
        default="real_world",
        description="'real_world' for external repos (Flask, Django, HA) or 'controlled_validation' for testbed",
    )
    total_tests_suite: Optional[int] = Field(
        default=None,
        description="Total test count discovered in test suite if known",
    )
    ground_truth: GroundTruth


class BaselineResult(BaseModel):
    """The test selection and latency result from a single baseline strategy."""

    baseline_type: BaselineType
    name: str
    selected_tests: list[str] = Field(default_factory=list)
    selected_count: int = 0
    total_tests: int = 0
    latency_ms: float = 0.0
    notes: str = ""


class EvaluationMetrics(BaseModel):
    """
    Strict mathematical evaluation metrics derived from predicted vs ground truth sets.
    Undefined denominators (e.g. 0/0) evaluate strictly to None (displaying N/A),
    never fabricated or assumed to be 1.0.
    """

    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1: Optional[float] = None
    test_reduction_pct: Optional[float] = None
    latency_ms: float = 0.0
    evolution_latency_ms: float = 0.0
    selection_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    is_evaluated: bool = False
    notes: str = ""


class TestSelectionEvidence(BaseModel):
    """Traceable evidence explaining why a specific test was selected by TestPilot."""

    test_name: str
    changed_symbol: str
    qualified_symbol: str
    caller_relationship: str  # "direct", "transitive_depth_2", etc.
    ast_evidence: str
    sourcegraph_evidence: Optional[str] = None
    match_quality: str  # "exact_qualified", "receiver_match", "heuristic_call"
    confidence: float = 1.0
    uncertainty: str = "low"
    resolution_engine: str = "AST"


class EvaluationRun(BaseModel):
    """
    Immutable, reproducible record of a completed benchmark evaluation run.
    Contains full environment metadata, commits, baselines, and evidence.
    """

    run_id: str
    case_id: str
    repository: str
    base_commit: str
    target_commit: str
    testpilot_version: Optional[str] = None
    python_version: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    prompt_version: Optional[str] = None
    rag_status: str = "disabled"
    total_tests: int = 0
    ground_truth_count: int = 0
    baseline_results: dict[str, BaselineResult] = Field(default_factory=dict)
    metrics: dict[str, EvaluationMetrics] = Field(default_factory=dict)
    evidence_records: list[TestSelectionEvidence] = Field(default_factory=list)
    timestamp: str
    status: str = "completed"
    notes: str = ""


class ComponentValidationResult(BaseModel):
    """
    Validation measurement for deterministic technical components against
    explicit ground truth expectations.
    """

    component_name: str
    metric_name: str
    correct_count: int
    total_count: int
    score_pct: float
    numerator_definition: str
    denominator_definition: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "passed"
