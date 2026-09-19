# TESTPILOT AI: PHASE 1 DEMO & EVALUATION SCRIPT
**Course:** CSE 4011: Intelligent Developer Tools and AI DevOps Workflows  
**Evaluation Weight:** 30% of Capstone Grade  
**Date:** Week of September 21, 2026  

---

## 1. Rubric Mapping & Verification Table

| Rubric Component | Weight | TestPilot Artifact / Verification Command | Expected Output |
| :--- | :--- | :--- | :--- |
| **Problem Definition & Charter** | 5% | Review `docs/SYNOPSIS.md` and `docs/ARCHITECTURE.md` | Clear formulation of "Spec-as-Oracle", comparison with TestForge, 4-person role matrix |
| **Sourcegraph & Semantic Navigation** | 10% | `testpilot check-sourcegraph`<br>`pytest tests/test_sourcegraph_client.py` | Demonstrates GraphQL query to Sourcegraph OSS and graceful fallback to AST code graph |
| **Prompt Engineering & BVA** | 5% | `testpilot generate-tests --file testbed/app/services/order_service.py --technique cot`<br>`pytest tests/test_prompts.py` | Shows CoT reasoning trace, boundary value discovery, and Pydantic schema validation |
| **Tool Configuration & Microservice Testbed** | 10% | `python -m testbed.app.main --export-openapi`<br>`pytest tests/ -v` | Running FastAPI testbed, valid OpenAPI 3.1 JSON export, reproducible monorepo layout |

---

## 2. Live Demo Script (Step-by-Step for Capstone Viva)

### Step 1: System Status & Health Check
Demonstrate that the environment is fully operational with local Ollama (`qwen2.5-coder:7b`) and AST fallback.
```bash
testpilot status
```
*Evaluator Commentary:* "Notice that TestPilot AI operates completely offline on local hardware with zero external API fees, detecting the Ollama model and local code graph."

### Step 2: Code Intelligence & AST Parsing
Demonstrate that TestPilot parses Python abstract syntax trees directly from git diffs without external dependencies:
```bash
testpilot parse-diff --file testbed/app/services/order_service.py
```
*Expected Terminal Output:*
- Displays extracted function signatures: `calculate_order_totals`, `apply_coupon`, `transition_order_status`.
- Shows boundary candidates automatically extracted:
  - Subtotal $\le 0$
  - Coupon discount exceeding total
  - Fractional cents rounding errors
  - Illegal status transition (`CANCELLED -> COMPLETED`).

### Step 3: Sourcegraph Semantic Navigation & Cross-Reference
Demonstrate how TestPilot queries caller hierarchies:
```bash
python -c "
from testpilot.sourcegraph.client import SourcegraphClient
client = SourcegraphClient()
callers = client.get_function_callers('calculate_order_totals', 'testbed/app/services/order_service.py')
print('Discovered Callers:', callers)
"
```
*Expected Output:*
- Demonstrates GraphQL call or graceful local AST fallback returning routes in `testbed/app/main.py` calling `calculate_order_totals`.

### Step 4: Prompt Engineering with Chain-of-Thought (CoT)
Execute test generation using local Ollama (`qwen2.5-coder:7b`):
```bash
testpilot generate-tests --file testbed/app/services/order_service.py --technique cot --output tests/generated/test_order_service.py
```
*Expected Output:*
- Terminal streams step-by-step CoT reasoning on boundary limits.
- Generates executable `pytest` code conforming to the Pydantic schema.

### Step 5: Bug Isolation & Spec-as-Oracle Arbitration
Run the synthesized test suite against the testbed:
```bash
pytest tests/generated/test_order_service.py -v
```
*Expected Output:*
- The tests catch the 3 intentional boundary bugs in the testbed microservice:
  1. Negative order total when discount exceeds cart value.
  2. Tax rounding truncation bug on boundary amounts.
  3. Illegal order status jump from `CANCELLED` to `COMPLETED`.
