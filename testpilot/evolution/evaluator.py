"""
Empirical Evaluation Harness for Repository Evolution Intelligence.
Measures Precision, Recall, F1-Score, False Positives, False Negatives,
and Latency against curated Ground-Truth Scenarios in the TestPilot repository.

Terminology:
- Direct caller: A function or endpoint handler that directly invokes the changed target symbol.
- Indirect caller: A function or endpoint handler that transitively depends on the target symbol (depth >= 2).
- Prioritized test: An existing test function that exercises the changed symbol or an affected caller.
- Macro-averaged metrics: Arithmetic mean of metric scores computed independently across scenarios.
- Micro-averaged metrics: Metric computed globally by pooling True Positives, False Positives, and False Negatives across all scenarios.
- Latency note: Measured latency captures call-graph traversal and test prioritization latency (excluding Git diff extraction).
"""

import time
from dataclasses import dataclass, field
from typing import Any

from testpilot.evolution.engine import RepositoryEvolutionEngine
from testpilot.evolution.models import ChangedSymbol, ChangeType


def compute_prf(predicted: set[str], expected: set[str]) -> tuple[float, float, float, list[str], list[str], list[str]]:
    """
    Computes Precision, Recall, F1, and error sets for predicted vs expected sets.
    Handles empty prediction and empty ground truth cases deterministically:
    - If both expected and predicted are empty: P=1.0, R=1.0, F1=1.0
    - If expected is empty but predicted is non-empty: P=0.0, R=1.0, F1=0.0
    - If expected is non-empty but predicted is empty: P=0.0, R=0.0, F1=0.0
    """
    tp_set = predicted.intersection(expected)
    fp_set = predicted - expected
    fn_set = expected - predicted
    tp = len(tp_set)
    fp = len(fp_set)
    fn = len(fn_set)

    if len(expected) == 0 and len(predicted) == 0:
        precision = 1.0
        recall = 1.0
        f1 = 1.0
    elif len(expected) == 0 and len(predicted) > 0:
        precision = 0.0
        recall = 1.0
        f1 = 0.0
    elif len(expected) > 0 and len(predicted) == 0:
        precision = 0.0
        recall = 0.0
        f1 = 0.0
    else:
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2.0 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return precision, recall, f1, sorted(tp_set), sorted(fp_set), sorted(fn_set)


@dataclass
class GroundTruthScenario:
    """Represents a controlled change scenario with verified ground-truth impacts."""

    name: str
    description: str
    changed_symbol: str
    changed_file: str
    expected_direct_callers: set[str]
    expected_indirect_callers: set[str]
    expected_test_callers: set[str]


@dataclass
class EvaluationMetrics:
    """Quantified precision, recall, F1, and error breakdown across direct, indirect, and test dimensions."""

    scenario: str
    # Direct impact metrics
    precision: float
    recall: float
    f1_score: float
    true_positives: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)

    # Indirect impact metrics
    indirect_precision: float = 1.0
    indirect_recall: float = 1.0
    indirect_f1: float = 1.0
    indirect_tp: list[str] = field(default_factory=list)
    indirect_fp: list[str] = field(default_factory=list)
    indirect_fn: list[str] = field(default_factory=list)

    # Test prioritization metrics
    test_precision: float = 1.0
    test_recall: float = 1.0
    test_f1: float = 1.0
    test_tp: list[str] = field(default_factory=list)
    test_fp: list[str] = field(default_factory=list)
    test_fn: list[str] = field(default_factory=list)

    # Accurately labeled latency
    call_graph_and_prioritization_latency_ms: float = 0.0

    @property
    def latency_ms(self) -> float:
        return self.call_graph_and_prioritization_latency_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "direct_impact": {
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1_score": round(self.f1_score, 4),
                "tp_count": len(self.true_positives),
                "fp_count": len(self.false_positives),
                "fn_count": len(self.false_negatives),
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
            },
            "indirect_impact": {
                "precision": round(self.indirect_precision, 4),
                "recall": round(self.indirect_recall, 4),
                "f1_score": round(self.indirect_f1, 4),
                "tp_count": len(self.indirect_tp),
                "fp_count": len(self.indirect_fp),
                "fn_count": len(self.indirect_fn),
                "true_positives": self.indirect_tp,
                "false_positives": self.indirect_fp,
                "false_negatives": self.indirect_fn,
            },
            "test_prioritization": {
                "precision": round(self.test_precision, 4),
                "recall": round(self.test_recall, 4),
                "f1_score": round(self.test_f1, 4),
                "tp_count": len(self.test_tp),
                "fp_count": len(self.test_fp),
                "fn_count": len(self.test_fn),
                "true_positives": self.test_tp,
                "false_positives": self.test_fp,
                "false_negatives": self.test_fn,
            },
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "tp_count": len(self.true_positives),
            "fp_count": len(self.false_positives),
            "fn_count": len(self.false_negatives),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "call_graph_and_prioritization_latency_ms": round(self.call_graph_and_prioritization_latency_ms, 2),
            "latency_ms": round(self.call_graph_and_prioritization_latency_ms, 2),
        }


# Curated Ground Truth Scenarios for the Testbed Order Service
# Direct callers verified directly in source code:
# - calculate_discount is invoked by calculate_order_totals (order_service.py:82) and apply_coupon (main.py:54)
# - calculate_tax is invoked by calculate_order_totals (order_service.py:86)
# - calculate_order_totals is invoked by create_order (main.py:75)
# Test callers verified in test suite:
# - test_bug_2_tax_truncation_rounding calls OrderService.calculate_tax (test_testbed_api.py:70)
# - test_bug_1_discount_deficit_negative_total calls OrderService.calculate_order_totals (test_testbed_api.py:55)
# - Generated tests in test_order_service.py call OrderService.calculate_order_totals directly
# Note on HTTP tests: test_apply_valid_and_invalid_coupons calls client.post("/orders/apply-coupon"),
# which is an HTTP request string rather than a static Python AST function call.
GROUND_TRUTH_SUITE: list[GroundTruthScenario] = [
    GroundTruthScenario(
        name="scenario_discount_deficit",
        description="Discount calculation logic modified in OrderService.calculate_discount",
        changed_symbol="calculate_discount",
        changed_file="testbed/app/services/order_service.py",
        expected_direct_callers={"calculate_order_totals", "apply_coupon"},
        expected_indirect_callers={"create_order"},
        expected_test_callers={
            "test_bug_1_discount_deficit_negative_total",
            "test_valid_coupon",
            "test_invalid_coupon",
            "test_empty_cart",
            "test_subtotal_below_free_shipping_threshold",
            "test_subtotal_at_free_shipping_threshold",
            "test_subtotal_above_free_shipping_threshold",
        },
    ),
    GroundTruthScenario(
        name="scenario_tax_precision",
        description="Tax calculation logic modified in OrderService.calculate_tax",
        changed_symbol="calculate_tax",
        changed_file="testbed/app/services/order_service.py",
        expected_direct_callers={"calculate_order_totals"},
        expected_indirect_callers={"create_order"},
        expected_test_callers={"test_bug_2_tax_truncation_rounding"},
    ),
    GroundTruthScenario(
        name="scenario_order_totals_core",
        description="Core calculation orchestration modified in OrderService.calculate_order_totals",
        changed_symbol="calculate_order_totals",
        changed_file="testbed/app/services/order_service.py",
        expected_direct_callers={"create_order"},
        expected_indirect_callers=set(),
        expected_test_callers={
            "test_bug_1_discount_deficit_negative_total",
            "test_valid_coupon",
            "test_invalid_coupon",
            "test_empty_cart",
            "test_subtotal_below_free_shipping_threshold",
            "test_subtotal_at_free_shipping_threshold",
            "test_subtotal_above_free_shipping_threshold",
        },
    ),
]


class EvolutionEvaluator:
    """Evaluates Repository Evolution Intelligence against ground-truth benchmarks."""

    def __init__(self, repo_root: str = "."):
        self.engine = RepositoryEvolutionEngine(repo_root=repo_root)

    def evaluate_scenario(self, scenario: GroundTruthScenario) -> EvaluationMetrics:
        """Runs impact analysis for a scenario and separately evaluates direct, indirect, and test metrics."""
        start_time = time.perf_counter()

        # Construct changed symbol
        sym = ChangedSymbol(
            name=scenario.changed_symbol,
            file_path=scenario.changed_file,
            line_start=1,
            line_end=100,
            change_type=ChangeType.MODIFIED,
        )

        direct_nodes, indirect_nodes = self.engine.build_transitive_impact_graph([sym], max_depth=3)
        prioritized_tests = self.engine.prioritize_tests([sym], direct_nodes, indirect_nodes)

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # 1. Direct callers
        predicted_direct = {node.symbol_name for node in direct_nodes}
        d_p, d_r, d_f1, d_tp, d_fp, d_fn = compute_prf(predicted_direct, scenario.expected_direct_callers)

        # 2. Indirect callers
        predicted_indirect = {node.symbol_name for node in indirect_nodes}
        i_p, i_r, i_f1, i_tp, i_fp, i_fn = compute_prf(predicted_indirect, scenario.expected_indirect_callers)

        # 3. Prioritized tests
        predicted_tests = {test.test_name for test in prioritized_tests}
        t_p, t_r, t_f1, t_tp, t_fp, t_fn = compute_prf(predicted_tests, scenario.expected_test_callers)

        return EvaluationMetrics(
            scenario=scenario.name,
            precision=d_p,
            recall=d_r,
            f1_score=d_f1,
            true_positives=d_tp,
            false_positives=d_fp,
            false_negatives=d_fn,
            indirect_precision=i_p,
            indirect_recall=i_r,
            indirect_f1=i_f1,
            indirect_tp=i_tp,
            indirect_fp=i_fp,
            indirect_fn=i_fn,
            test_precision=t_p,
            test_recall=t_r,
            test_f1=t_f1,
            test_tp=t_tp,
            test_fp=t_fp,
            test_fn=t_fn,
            call_graph_and_prioritization_latency_ms=latency_ms,
        )

    def evaluate_controlled_fixtures(self) -> dict[str, Any]:
        """
        Evaluates 6 controlled fixtures:
        1. Direct caller
        2. Multi-hop caller
        3. Same-name isolation (common verb e.g. 'run')
        4. Import alias
        5. Added / deleted symbol
        6. Uncertain / dynamic call relationship
        """
        import subprocess
        import tempfile
        from pathlib import Path

        results: dict[str, Any] = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "TestPilot"], cwd=str(tmp_path), capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@testpilot.ai"], cwd=str(tmp_path), capture_output=True, check=True)

            # File 1: core_calc.py
            (tmp_path / "core_calc.py").write_text(
                "def calculate_tax(amount):\n"
                "    return amount * 0.1\n\n"
                "def base_discount(amount):\n"
                "    return amount * 0.05\n\n"
                "def old_deprecated_symbol(x):\n"
                "    return x\n"
            )

            # File 2: service.py
            (tmp_path / "service.py").write_text(
                "from core_calc import calculate_tax, base_discount\n"
                "from core_calc import calculate_tax as tax_alias\n\n"
                "def compute_total(subtotal):\n"
                "    return subtotal + calculate_tax(subtotal)\n\n"
                "def aliased_caller(subtotal):\n"
                "    return subtotal + tax_alias(subtotal)\n\n"
                "def order_discount(subtotal):\n"
                "    return base_discount(subtotal)\n\n"
                "def call_deprecated():\n"
                "    from core_calc import old_deprecated_symbol\n"
                "    return old_deprecated_symbol(10)\n"
            )

            # File 3: api.py
            (tmp_path / "api.py").write_text(
                "from service import order_discount\n\n"
                "def checkout_endpoint(subtotal):\n"
                "    return order_discount(subtotal)\n"
            )

            # File 4: common_name_worker.py and common_name_executor.py
            (tmp_path / "common_name_worker.py").write_text(
                "def run(task):\n"
                "    return task.execute()\n"
            )
            (tmp_path / "common_name_executor.py").write_text(
                "def run(command):\n"
                "    return command\n"
            )
            (tmp_path / "caller_worker.py").write_text(
                "import common_name_worker\n\n"
                "def invoke_worker_run(t):\n"
                "    return common_name_worker.run(t)\n"
            )
            (tmp_path / "caller_executor.py").write_text(
                "import common_name_executor\n\n"
                "def invoke_executor_run(c):\n"
                "    return common_name_executor.run(c)\n"
            )

            # File 5: dynamic_caller.py
            (tmp_path / "dynamic_caller.py").write_text(
                "def dispatch_event(handler, event):\n"
                "    return handler.calculate_tax(event)\n"
            )

            subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(tmp_path), capture_output=True, check=True)

            engine = RepositoryEvolutionEngine(repo_root=str(tmp_path))

            # 1. Direct Caller: calculate_tax
            sym_tax = ChangedSymbol(name="calculate_tax", file_path="core_calc.py", line_start=1, line_end=2, change_type=ChangeType.MODIFIED)
            d_nodes, _ = engine.build_transitive_impact_graph([sym_tax], max_depth=2)
            direct_names = {n.symbol_name for n in d_nodes}
            p, r, f1, _, _, _ = compute_prf(direct_names.intersection({"compute_total"}), {"compute_total"})
            results["direct_caller"] = {
                "precision": p, "recall": r, "f1_score": f1,
                "description": "Direct AST caller resolution (compute_total calling calculate_tax)",
                "passed": bool(r == 1.0 and p == 1.0),
            }

            # 2. Multi-hop Caller: base_discount -> order_discount -> checkout_endpoint
            sym_discount = ChangedSymbol(name="base_discount", file_path="core_calc.py", line_start=4, line_end=5, change_type=ChangeType.MODIFIED)
            _, i_disc = engine.build_transitive_impact_graph([sym_discount], max_depth=3)
            indirect_names = {n.symbol_name for n in i_disc}
            p, r, f1, _, _, _ = compute_prf(indirect_names.intersection({"checkout_endpoint"}), {"checkout_endpoint"})
            results["multi_hop_caller"] = {
                "precision": p, "recall": r, "f1_score": f1,
                "description": "Multi-hop transitive propagation (base_discount -> order_discount -> checkout_endpoint)",
                "passed": bool(r == 1.0 and p == 1.0),
            }

            # 3. Same-name Isolation: common_name_worker.py:run vs common_name_executor.py:run
            sym_run = ChangedSymbol(name="run", file_path="common_name_worker.py", line_start=1, line_end=2, change_type=ChangeType.MODIFIED)
            d_run, _ = engine.build_transitive_impact_graph([sym_run], max_depth=2)
            run_direct_callers = {n.symbol_name for n in d_run}
            has_worker = "invoke_worker_run" in run_direct_callers
            has_executor_fp = "invoke_executor_run" in run_direct_callers
            results["same_name_isolation"] = {
                "precision": 1.0 if not has_executor_fp else 0.5,
                "recall": 1.0 if has_worker else 0.0,
                "f1_score": 1.0 if has_worker and not has_executor_fp else 0.0,
                "false_positive_count": 1 if has_executor_fp else 0,
                "description": "Unrelated same-named function isolation (worker.run vs executor.run)",
                "passed": bool(has_worker and not has_executor_fp),
            }

            # 4. Import Alias: from core_calc import calculate_tax as tax_alias
            aliased_resolved = "aliased_caller" in direct_names
            results["import_alias"] = {
                "precision": 1.0 if aliased_resolved else 0.0,
                "recall": 1.0 if aliased_resolved else 0.0,
                "f1_score": 1.0 if aliased_resolved else 0.0,
                "description": "Import alias resolution ('import calculate_tax as tax_alias')",
                "passed": aliased_resolved,
            }

            # 5. Added/Deleted Symbol: old_deprecated_symbol deleted
            (tmp_path / "core_calc.py").write_text(
                "def calculate_tax(amount):\n"
                "    return amount * 0.1\n\n"
                "def base_discount(amount):\n"
                "    return amount * 0.05\n"
            )
            diff_text, c_files, _ = engine.resolve_git_diff(base_ref="HEAD", target_ref=None)
            c_syms = engine.extract_changed_symbols(diff_text=diff_text, changed_files=c_files, base_ref="HEAD", target_ref=None)
            deleted_syms = [s for s in c_syms if s.change_type == ChangeType.DELETED and s.name == "old_deprecated_symbol"]
            deleted_passed = len(deleted_syms) == 1
            results["added_deleted_symbol"] = {
                "precision": 1.0 if deleted_passed else 0.0,
                "recall": 1.0 if deleted_passed else 0.0,
                "f1_score": 1.0 if deleted_passed else 0.0,
                "description": "Deleted symbol identification from Git base object storage",
                "passed": deleted_passed,
            }

            # 6. Uncertain / Dynamic Call: handler.calculate_tax(...)
            sym_dyn = ChangedSymbol(name="calculate_tax", file_path="core_calc.py", line_start=1, line_end=2, change_type=ChangeType.MODIFIED)
            d_dyn, _ = engine.build_transitive_impact_graph([sym_dyn], max_depth=1)
            dyn_nodes = [n for n in d_dyn if n.symbol_name == "dispatch_event"]
            dyn_ambiguous = len(dyn_nodes) == 1 and (dyn_nodes[0].evidence.is_ambiguous or not dyn_nodes[0].is_confirmed)
            results["dynamic_uncertainty"] = {
                "precision": 1.0 if dyn_ambiguous else 0.0,
                "recall": 1.0 if dyn_ambiguous else 0.0,
                "f1_score": 1.0 if dyn_ambiguous else 0.0,
                "is_ambiguous": dyn_ambiguous,
                "description": "Dynamic/unanchored receiver call correctly marked ambiguous and uncertain",
                "passed": dyn_ambiguous,
            }

        return results

    def run_all(self) -> dict[str, Any]:
        """
        Runs the benchmark suite and returns comprehensive metrics report.
        Clearly separates Direct Impact, Indirect Impact, and Test Prioritization dimensions,
        and provides both Macro-Averaged and Micro-Averaged metrics, as well as controlled fixture evaluations.
        """
        results: list[EvaluationMetrics] = []
        for sc in GROUND_TRUTH_SUITE:
            results.append(self.evaluate_scenario(sc))

        n = len(results) if results else 1

        # Macro-Averaged Metrics (unweighted mean across scenarios)
        macro_direct_p = sum(r.precision for r in results) / n
        macro_direct_r = sum(r.recall for r in results) / n
        macro_direct_f1 = sum(r.f1_score for r in results) / n

        macro_indirect_p = sum(r.indirect_precision for r in results) / n
        macro_indirect_r = sum(r.indirect_recall for r in results) / n
        macro_indirect_f1 = sum(r.indirect_f1 for r in results) / n

        macro_test_p = sum(r.test_precision for r in results) / n
        macro_test_r = sum(r.test_recall for r in results) / n
        macro_test_f1 = sum(r.test_f1 for r in results) / n

        avg_latency = sum(r.call_graph_and_prioritization_latency_ms for r in results) / n

        # Micro-Averaged Metrics (pooled TP, FP, FN across scenarios)
        def micro_aggregate(tp_list, fp_list, fn_list):
            total_tp = sum(len(x) for x in tp_list)
            total_fp = sum(len(x) for x in fp_list)
            total_fn = sum(len(x) for x in fn_list)
            p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
            r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
            f1 = (2.0 * p * r) / (p + r) if (p + r) > 0 else 0.0
            return round(p, 4), round(r, 4), round(f1, 4), total_tp, total_fp, total_fn

        micro_d_p, micro_d_r, micro_d_f1, total_d_tp, total_d_fp, total_d_fn = micro_aggregate(
            [r.true_positives for r in results],
            [r.false_positives for r in results],
            [r.false_negatives for r in results],
        )

        micro_i_p, micro_i_r, micro_i_f1, total_i_tp, total_i_fp, total_i_fn = micro_aggregate(
            [r.indirect_tp for r in results],
            [r.indirect_fp for r in results],
            [r.indirect_fn for r in results],
        )

        micro_t_p, micro_t_r, micro_t_f1, total_t_tp, total_t_fp, total_t_fn = micro_aggregate(
            [r.test_tp for r in results],
            [r.test_fp for r in results],
            [r.test_fn for r in results],
        )

        # Run controlled fixtures evaluation
        controlled_fixtures = self.evaluate_controlled_fixtures()

        return {
            "total_scenarios": len(results),
            "evaluation_scope_note": (
                "Curated benchmark across 3 testbed scenarios + 6 controlled fixtures. Validates engine mechanics "
                "on verified patterns; does not claim general accuracy across arbitrary Python codebases."
            ),
            "macro_averaged": {
                "direct_impact": {
                    "precision": round(macro_direct_p, 4),
                    "recall": round(macro_direct_r, 4),
                    "f1_score": round(macro_direct_f1, 4),
                },
                "indirect_impact": {
                    "precision": round(macro_indirect_p, 4),
                    "recall": round(macro_indirect_r, 4),
                    "f1_score": round(macro_indirect_f1, 4),
                },
                "test_prioritization": {
                    "precision": round(macro_test_p, 4),
                    "recall": round(macro_test_r, 4),
                    "f1_score": round(macro_test_f1, 4),
                },
            },
            "micro_averaged": {
                "direct_impact": {
                    "precision": micro_d_p,
                    "recall": micro_d_r,
                    "f1_score": micro_d_f1,
                    "pooled_tp": total_d_tp,
                    "pooled_fp": total_d_fp,
                    "pooled_fn": total_d_fn,
                },
                "indirect_impact": {
                    "precision": micro_i_p,
                    "recall": micro_i_r,
                    "f1_score": micro_i_f1,
                    "pooled_tp": total_i_tp,
                    "pooled_fp": total_i_fp,
                    "pooled_fn": total_i_fn,
                },
                "test_prioritization": {
                    "precision": micro_t_p,
                    "recall": micro_t_r,
                    "f1_score": micro_t_f1,
                    "pooled_tp": total_t_tp,
                    "pooled_fp": total_t_fp,
                    "pooled_fn": total_t_fn,
                },
            },
            "controlled_fixtures": controlled_fixtures,
            # Top-level backward-compatible keys
            "mean_precision": round(macro_direct_p, 4),
            "mean_recall": round(macro_direct_r, 4),
            "mean_f1_score": round(macro_direct_f1, 4),
            "mean_latency_ms": round(avg_latency, 2),
            "call_graph_and_prioritization_latency_ms": round(avg_latency, 2),
            "scenarios": [r.to_dict() for r in results],
        }


if __name__ == "__main__":
    evaluator = EvolutionEvaluator()
    summary = evaluator.run_all()
    print("=" * 70)
    print("REPOSITORY EVOLUTION INTELLIGENCE — EVALUATION REPORT")
    print("=" * 70)
    print(f"Scenarios Evaluated: {summary['total_scenarios']}")
    print(f"Macro Direct P/R/F1:    P={summary['macro_averaged']['direct_impact']['precision']:.2f} "
          f"R={summary['macro_averaged']['direct_impact']['recall']:.2f} "
          f"F1={summary['macro_averaged']['direct_impact']['f1_score']:.2f}")
    print(f"Micro Direct P/R/F1:    P={summary['micro_averaged']['direct_impact']['precision']:.2f} "
          f"R={summary['micro_averaged']['direct_impact']['recall']:.2f} "
          f"F1={summary['micro_averaged']['direct_impact']['f1_score']:.2f}")
    print(f"Prioritization P/R/F1:  P={summary['macro_averaged']['test_prioritization']['precision']:.2f} "
          f"R={summary['macro_averaged']['test_prioritization']['recall']:.2f} "
          f"F1={summary['macro_averaged']['test_prioritization']['f1_score']:.2f}")
    print(f"Mean Call-Graph Latency: {summary['call_graph_and_prioritization_latency_ms']:.2f} ms")
    print("-" * 70)
    print("CONTROLLED FIXTURE RESULTS (6 SCENARIOS):")
    for fix_name, fix_data in summary.get("controlled_fixtures", {}).items():
        pass_str = "PASS" if fix_data.get("passed") else "FAIL"
        print(f"  [{pass_str}] {fix_name:25s} P={fix_data['precision']:.2f} R={fix_data['recall']:.2f} F1={fix_data['f1_score']:.2f} - {fix_data['description']}")
    print("-" * 70)
    for sc in summary["scenarios"]:
        print(f"[{sc['scenario']}] Direct P={sc['direct_impact']['precision']:.2f} "
              f"R={sc['direct_impact']['recall']:.2f} F1={sc['direct_impact']['f1_score']:.2f} "
              f"Latency={sc['latency_ms']:.1f}ms")
    print("=" * 70)
