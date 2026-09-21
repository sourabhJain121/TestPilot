"""
TestPilot AI Empirical Benchmarking Subsystem.
Compares local LLMs (Qwen2.5-Coder, CodeLlama) against industry baselines
(Schemathesis, Code-as-Oracle) on seeded testbed boundary defects.
"""

from testpilot.benchmark.evaluator import BenchmarkEvaluator, BenchmarkResult
from testpilot.benchmark.runner import BenchmarkRunner, run_benchmark

__all__ = [
    "BenchmarkResult",
    "BenchmarkEvaluator",
    "BenchmarkRunner",
    "run_benchmark",
]
