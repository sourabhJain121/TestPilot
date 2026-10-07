"""
TestPilot Evaluation Subsystem.
Provides empirical benchmarking, baseline comparisons (Full Regression,
Naive Name-Based Selection, TestPilot Qualified Identity), deterministic
ground-truth evaluation, and component-level correctness verification.
"""

from testpilot.evaluation.engine import EvaluationEngine
from testpilot.evaluation.models import (
    BaselineResult,
    BaselineType,
    BenchmarkCase,
    ComponentValidationResult,
    EvaluationMetrics,
    EvaluationRun,
    GroundTruth,
    TestSelectionEvidence,
)
from testpilot.evaluation.storage import EvaluationStorage

__all__ = [
    "BaselineResult",
    "BaselineType",
    "BenchmarkCase",
    "ComponentValidationResult",
    "EvaluationEngine",
    "EvaluationMetrics",
    "EvaluationRun",
    "EvaluationStorage",
    "GroundTruth",
    "TestSelectionEvidence",
]
