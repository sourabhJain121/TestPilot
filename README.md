# 🚀 TestPilot — Evidence-Grounded AI for Change-Aware Regression Testing

### Repository Evolution Intelligence &rarr; Specification-Grounded Testing &rarr; Three-Valued Failure Arbitration

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Tree-Sitter](https://img.shields.io/badge/AST-Tree--sitter_0.21%2B-5c2d91.svg)](https://tree-sitter.github.io)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.5%2B-e92063.svg)](https://docs.pydantic.dev)
[![ChromaDB](https://img.shields.io/badge/Vector_DB-ChromaDB-purple.svg)](https://www.trychroma.com)
[![Local LLM](https://img.shields.io/badge/Local_LLM-Ollama_CodeLlama_&_Qwen-orange.svg)](https://ollama.ai)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 1. Project Title & Research Positioning

**Project**: TestPilot
**Tagline**: Evidence-Grounded AI for Change-Aware Regression Testing

> [!IMPORTANT]
> **Core vs. Experimental Distinction**:
> - **CORE / VALIDATED**: Deterministic TestPilot (Git Diff + AST/Tree-sitter + Qualified `SymbolId` + Caller Graph + OpenAPI Deterministic Matrix + Spec-as-Oracle Three-Valued Arbitration).
> - **CORE / INTEGRATED WITH FALLBACK**: Sourcegraph Code Intelligence (GraphQL symbol/reference search with autonomous local AST fallback).
> - **EXPERIMENTAL**: Repository Code RAG (`repo_code_store` semantic indexing) & CodeLlama Semantic Test Validation (`codellama:7b` behavioral reasoning).
> - **EXPERIMENTAL / OPTIONAL EXTENSION**: Autonomous Code Remediation (Sweep.dev pattern patch generation and sandbox verification).
>
> Quantitative claim integrity: Repository RAG and CodeLlama semantic validation have been implemented and validated functionally; quantitative empirical benchmark impact remains under research evaluation.

---

## 2. Problem Statement & Motivation

Modern software engineering CI/CD pipelines run thousands of regression tests on every pull request, causing test bloat, delayed feedback cycles, and prohibitive compute costs. Existing regression test selection (RTS) tools either:
1. **Naive Name / Token Matching**: Blindly match function names, suffering catastrophic false positive collisions on common identifiers (`__init__`, `run`, `handle`, `update`).
2. **Pure Dynamic Tracing**: Require expensive test runs with instrumentation on every commit, failing to generalize to modified or unrun branches.
3. **Pure LLM Generation**: Suffer from hallucination, brittle assertions, and lack of repository structural context.

TestPilot solves this by combining **deterministic repository evidence** (Git diffs, AST/Tree-sitter syntactic analysis, qualified symbol tracking, Sourcegraph code search) with **specification grounding** and **optional LLM semantic reasoning**.

---

## 3. Primary & Secondary Research Questions

- **Primary Research Question**:
  > *"Can repository-aware AI-assisted impact analysis accurately identify regression tests affected by software changes while reducing unnecessary test execution?"*
- **Secondary Research Question**:
  > *"Does combining deterministic repository evidence with LLM-based semantic reasoning improve the reliability of regression-test selection and failure classification compared with simpler baselines?"*

---

## 4. Key Contributions

1. **Qualified Symbol Identity (`SymbolId`)**: Tracks code entities by canonical namespace (`module.Class.method`), completely eliminating generic-token false positive collisions.
2. **Deterministic OpenAPI Boundary Matrix**: Extracts formal input domain partitions (boundary values, enum edge-cases, nullability) without stochastic hallucination.
3. **Three-Valued Failure Arbitration**: Distinguishes true software bugs (`TRUE_CODE_DEFECT`) from invalid tests (`INVALID_TEST_ASSERTION`) and unclear contracts (`SPEC_AMBIGUITY_OR_DEFECT`).
4. **Sourcegraph Code Intelligence**: Augments local AST analysis with multi-hop definition, reference, and test finding, with autonomous local AST fallback.
5. **Repository Code RAG (Experimental)**: Dedicated vector collection (`repo_code_store`) capturing AST-bounded semantic units (functions, classes, methods) with qualified symbol metadata.
6. **CodeLlama Semantic Validation (Experimental)**: Evaluates behavioral test relevance with **Critical Recall Protection** guaranteeing confirmed deterministic candidates are never dropped.
7. **Empirical Evaluation Subsystem**: Traceable, mathematically rigorous benchmarking measuring Precision, Recall, F1, and Test Reduction across real repositories (Flask, Django, Home Assistant).

---

## 5. System Architecture & Unified End-to-End Operational Workflow

TestPilot provides a single, coherent end-to-end repository workflow where you select and analyze a repository once (such as Pallets Flask, Django, or Local Testbed), and all downstream stages operate strictly on that **same repository and analysis context**.

```
[Stage 0: Repository Evolution Intelligence]
   Git Diff (base..target) ──> AST Syntax Parsing ──> SymbolId ──> Transitive Blast Radius
         │  (Initializes ActiveAnalysisContext with unique analysis_id)
         ▼
[Stage 1: Specification & Boundaries]
   Honest Spec Detection: OpenAPI 3.1 (if available) OR AST Source Decision Boundaries (if no spec)
         │  (Consumes primary_target_file & primary_target_symbol from active context)
         ▼
[Stage 2: Deterministic Boundary Matrix]
   Synthesizes edge cases & bounds (Evidence: OpenAPI vs AST Source Code Boundaries — Zero Hallucination)
         │
         ▼
[Stage 3: Impact Analysis & Code Intelligence]
   Upstream caller hierarchy & dependency traversal on active repository symbols
         │
         ▼
[Stage 4: Test Generation & Execution]
   Prioritized regression suite execution (nested subprocess protected by TESTPILOT_PIPELINE_DEPTH)
         │
         ▼
[Stage 5: Spec-as-Oracle Failure Arbitration]
   Multi-source evidence fusion: Three-valued classification (True Defect vs Invalid Test vs Spec Ambiguity)
         │
         ▼
[Stage 6: Pipeline Complete] ✓
```

### Key Workflow Architectural Principles:
1. **Single Source of Truth (`ActiveAnalysisContext`)**:
   - Repository Evolution establishes the active analysis context (`/api/analysis/context`), generating a unique `analysis_id` (`#run-YYYYMMDD-xxxxxx`), resolving the human-readable repository name, detecting OpenAPI specification availability, and isolating the primary target file and symbols.
2. **Deterministic Context Propagation**:
   - Downstream stages (AST extraction, Deterministic Matrix, Impact Analysis, Failure Arbitration) read directly from the active analysis context. They **never silently revert** to hardcoded testbed files (e.g. `order_service.py`) when analyzing external repositories like Flask or Django.
3. **Honest Specification Policy**:
   - Repositories without OpenAPI definitions (such as Flask or Django) explicitly declare: `Specification: Not available for this repository` with zero-hallucination messaging (*"Repository-level boundary analysis can continue using available source-code evidence."*). Deterministic boundary synthesis safely extracts branch boundary conditions from AST source code without inventing nonexistent OpenAPI routes.
4. **Persistent Active Context Bar & Navigation**:
   - A dedicated banner remains visible across all workflow panels showing the Active Repository, Target File & Symbol, Spec Status, and Run ID, with one-click "Next →" transitions and a "Reset / New Analysis" controller.
5. **Safe External Execution**:
   - External repositories without required host dependencies are safely handled with explicit environment limitation reporting rather than injecting fake testbed passes.

*Note: Evaluation and Autonomous Remediation are separate standalone modules and do NOT intrude into the operational workflow.*

---

## 6. Core Modules

### A. Repository Evolution Intelligence (CORE)
- **Git Diff Engine**: Analyzes unified git diffs between arbitrary base and target refs (`HEAD~1`, commits, branches, or working tree).
- **AST / Tree-sitter Parser**: Extracts modified functions, methods, classes, parameters, and boundary conditions.
- **Qualified Symbol Identity (`SymbolId`)**: Maps symbols to `path/to/module.py:ClassName.method_name`.
- **Transitive Blast Radius**: Graph traversal computing direct (1-hop) and indirect (multi-hop) dependencies up to depth 5.
- **Explainable Test Prioritization**: Ranks candidate regression tests into `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW` tiers with token-boundary matching and structured evidence trails.

### B. Sourcegraph Code Intelligence (CORE / FALLBACK SAFE)
- **Client**: Queries Sourcegraph GraphQL endpoint (`http://localhost:7080/.api/graphql`) or remote instance.
- **Capabilities**:
  - `find_definitions(symbol)`: Symbol definition locations.
  - `find_references(symbol)`: Call sites and usages.
  - `find_test_references(symbol)`: Test files referencing symbol.
  - `find_class_usages(class_name)`: Class instantiations and subclasses.
  - `search_code(query)` & `search_functions(func_name)`: Code search.
- **Evidence Normalization**: Normalizes results into `AVAILABLE_EVIDENCE_FOUND`, `AVAILABLE_NO_EVIDENCE`, or `SOURCEGRAPH_UNAVAILABLE_FALLBACK`.
- **Autonomous Fallback**: If Sourcegraph is offline, automatically switches to `LocalCodeGraphFallback` (AST search) without disrupting pipeline execution.

### C. Repository Code RAG (EXPERIMENTAL)
- **Vector Database**: Dedicated ChromaDB collection (`repo_code_store`) inside `.chroma_db/`. (Completely separate from `spec_store`).
- **Semantic Code Units**: Indexes functions, methods, classes, and test functions rather than arbitrary fixed-size chunking.
- **Metadata**: Each chunk stores qualified symbol identity, file path, symbol type, line range, docstring, parameters, and `is_test` boolean.
- **Deterministic Deduplication**: Uses deterministic IDs `repo_code::{file_path}::{qualified_symbol}` to prevent duplicate indexing across runs.
- **Retrieval**: `retrieve_code_context(query, top_k)` using local sentence-transformers embeddings (`all-MiniLM-L6-v2`).

### D. CodeLlama Semantic Validation (EXPERIMENTAL)
- **Validator**: `SemanticTestValidator` using `codellama:7b` (configurable via `SEMANTIC_VALIDATOR_MODEL`).
- **Prompt Evidence**: Combines Candidate Test + Changed Symbol + Git Diff + AST EvidenceTrail + Sourcegraph Evidence + Retrieved Repository Context.
- **Decisions**: Structured Pydantic model `SemanticValidationResult` outputting `HIGH`, `MEDIUM`, or `LOW`.
- **Critical Recall Protection**: Confirmed deterministic candidates (`CRITICAL` or `HIGH` direct call) are **never dropped** if CodeLlama returns `LOW`. RAG and CodeLlama primarily refine uncertain or heuristic candidates.

### E. Specification-Grounded Testing & Three-Valued Arbitration (CORE)
- **Boundary Engine**: Extracts formal boundary conditions (minimum, maximum, regex patterns, enum values) from OpenAPI 3.1 schemas.
- **Test Generation**: Generates targeted boundary tests with Qwen2.5-Coder (`qwen2.5-coder:7b`).
- **Arbitration Engine**: Three-valued classifier:
  - `TRUE_CODE_DEFECT`: Implementation deviates from unambiguous specification contract.
  - `INVALID_TEST_ASSERTION`: Test asserts conditions contrary to schema or contract.
  - `SPEC_AMBIGUITY_OR_DEFECT`: Specification contract is incomplete, conflicting, or underspecified.

### F. Pipeline Recursion Guard (CRITICAL ARCHITECTURE)
To prevent recursive pytest execution when running regression suites from within pipeline tests:
- Uses `TESTPILOT_PIPELINE_DEPTH` environment variable tracking execution depth.
- Top-level pipeline executes at depth 0; child pytest processes inherit depth 1 via `child_env`.
- If a child test invokes the pipeline, it detects depth &ge; 1 and executes safely without spawning nested subprocesses.
- Includes a 15-second subprocess execution timeout per child test.

---

## 7. Empirical Evaluation Subsystem

The evaluation harness benchmark evaluates test selection approaches against ground truth:

| Baseline | Strategy | Methodology |
| :--- | :--- | :--- |
| **Full Regression** | 100% of discovered tests | Standard CI exhaustiveness (0% reduction) |
| **Naive Name Matching** | Bare token substring match | Token matching without qualified symbol checking |
| **TestPilot (Qualified Identity)** | Qualified AST + receiver graph | Evidence-grounded qualified symbol identity |
| **TestPilot + Repository RAG** | Deterministic + Vector RAG + CodeLlama | Semantic validation with Critical Recall Protection |

### Benchmarked Results (Positive-Ground-Truth Pooled Suite: Testbed + Flask)

- **Total Benchmarked Tests**: 10,713 tests
- **Ground Truth Callers**: 20 verified callers
- **Full Regression**: Precision: 0.23% | Recall: 100.00% | F1: 0.46% | Test Reduction: 0.00%
- **Naive Name Matching**: Precision: 11.61% | Recall: 65.00% | F1: 19.70% | Test Reduction: 98.86%
- **TestPilot (Qualified Identity)**: **Precision: 15.31%** | **Recall: 75.00%** | **F1: 25.43%** | **Test Reduction: 99.07%**

### Negative Control Case Study (Home Assistant Core)
- **Ground Truth**: 0 callers in commit
- **Naive Name Matching**: 19 False Positives (bare `__init__` token collisions)
- **TestPilot**: **0 False Positives (100% Rejection)** via receiver-scoped resolution

---

## 8. Installation & Environment Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.14)
- Git 2.25+
- (Optional) [Ollama](https://ollama.ai) with models:
  ```bash
  ollama pull qwen2.5-coder:7b
  ollama pull codellama:7b
  ```
- (Optional) [Sourcegraph](https://sourcegraph.com): Local Docker container on port 7080 or remote instance.

### Setup
```bash
# 1. Clone repository
git clone https://github.com/sourabhJain121/TestPilot.git
cd TestPilot

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies in editable mode
pip install -e .
```

---

## 9. Running TestPilot

### A. Run System Diagnostics
```bash
./.venv/bin/testpilot status
```

### B. Run Deterministic Baseline Pipeline
```bash
./.venv/bin/testpilot pipeline --base HEAD~1 --target HEAD --spec-path testbed/openapi.json
```

### C. Run Experimental Pipeline with Repository RAG & CodeLlama
```bash
./.venv/bin/testpilot pipeline --enable-semantic-validation
```

### D. Run Repository Code RAG CLI Commands
```bash
# Index current repository into ChromaDB repo_code_store
./.venv/bin/testpilot rag-index --repo-path .

# Query repository semantic code context
./.venv/bin/testpilot rag-query "calculate order totals" --top-k 3
```

### E. Run Sourcegraph Code Intelligence CLI
```bash
# Query references (with automatic local AST fallback if offline)
./.venv/bin/testpilot sourcegraph-query calculate_total --type references

# Query definitions
./.venv/bin/testpilot sourcegraph-query OrderService --type definitions
```

### F. Run Evaluation Harness
```bash
# View evaluation overview
./.venv/bin/testpilot evaluate

# Run all benchmark cases
./.venv/bin/testpilot evaluate --all
```

### G. Launch Web Dashboard
```bash
# Start backend server
./.venv/bin/uvicorn testpilot.web.api:app --host 127.0.0.1 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 10. Web API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **System** |||
| `GET` | `/api/status` | System health check (Ollama, Sourcegraph, ChromaDB, Python) |
| `POST` | `/api/settings/model` | Switch active LLM model |
| **Pipeline** |||
| `POST` | `/api/pipeline/run` | Execute 6-stage autonomous pipeline (supports `enable_semantic_validation`) |
| `POST` | `/api/evolution/analyze` | Repository evolution intelligence & blast radius analysis |
| `GET` | `/api/evolution/refs` | Query symbol references via evolution engine |
| `POST` | `/api/ast/parse-diff` | Parse git diff and extract AST-level changes |
| **Code Intelligence** |||
| `GET` | `/api/code-intel/status` | Sourcegraph / local fallback connection status |
| `GET` | `/api/code-intel/search` | Unified code search (definitions, references, tests, functions) |
| `GET` | `/api/code-intel/callers` | Find callers of a symbol |
| `GET` | `/api/code-intel/source` | Retrieve source code for a file |
| `GET` | `/api/sourcegraph/definitions` | Symbol definition locations |
| `GET` | `/api/sourcegraph/references` | Symbol reference / call sites |
| `GET` | `/api/sourcegraph/tests` | Test files referencing a symbol |
| `GET` | `/api/sourcegraph/class-usages` | Class instantiations and subclasses |
| **RAG & Test Generation** |||
| `POST` | `/api/rag/index` | Index repository semantic code units into ChromaDB |
| `POST` | `/api/rag/query` | Retrieve code context from `repo_code_store` |
| `POST` | `/api/testgen/deterministic` | Generate deterministic boundary tests from OpenAPI spec |
| `POST` | `/api/verify` | Execute generated tests and classify failures |
| **Evaluation** |||
| `GET` | `/api/evaluation/overview` | Pooled benchmark metrics and baseline comparisons |
| `GET` | `/api/evaluation/benchmarks` | List all benchmark cases |
| `GET` | `/api/evaluation/benchmarks/{case_id}` | Get a specific benchmark case |
| `GET` | `/api/evaluation/components` | Component-level evaluation metrics |
| `GET` | `/api/evaluation/failure-analysis` | Failure classification analysis |
| `POST` | `/api/evaluation/run` | Execute benchmark case evaluation |
| **Remediation & Guardrails** |||
| `POST` | `/api/remediate` | Autonomous patch synthesis for failing tests |
| `POST` | `/api/guardrails/check` | Safety guardrail check on generated code |
| `GET` | `/api/guardrails/audit` | Audit log of guardrail checks |
| **Repository** |||
| `POST` | `/api/repo/load` | Load external repository for analysis |
| `POST` | `/api/repo/zero-clone-testgen` | Zero-clone test generation for external repos |
| `POST` | `/api/report/export` | Export analysis report |
| `GET` | `/api/benchmark` | Benchmark data endpoint |

---

## 11. Running Automated Tests

```bash
# 1. Run linting
./.venv/bin/ruff check testpilot tests

# 2. Run Sourcegraph tests
./.venv/bin/pytest tests/test_sourcegraph_client.py -v

# 3. Run Repository RAG tests
./.venv/bin/pytest tests/test_repo_vector_store.py -v

# 4. Run CodeLlama Semantic Validator tests
./.venv/bin/pytest tests/test_semantic_validator.py -v

# 5. Run RAG Pipeline Integration tests
./.venv/bin/pytest tests/test_rag_pipeline_integration.py -v

# 6. Run Web API tests
./.venv/bin/pytest tests/test_web_api.py -v

# 7. Run Evaluation Subsystem tests
./.venv/bin/pytest tests/test_evaluation_subsystem.py -v

# 8. Run full test suite
./.venv/bin/pytest
```

---

## 12. Project Structure

```
TestPilot/
├── testpilot/
│   ├── ast_engine/          # Tree-sitter & AST diff parsers
│   ├── benchmark/           # Benchmark runners & evaluators
│   ├── core/
│   │   ├── models.py        # Core request/response schemas
│   │   └── pipeline.py      # FullPipelineOrchestrator & recursion protection
│   ├── evolution/
│   │   ├── engine.py        # RepositoryEvolutionEngine & blast radius
│   │   └── models.py        # SymbolId, EvidenceTrail, PrioritizedTest
│   ├── evaluation/
│   │   ├── baselines.py     # Full Regression, Naive, TestPilot, TestPilot+RAG
│   │   ├── engine.py        # EvaluationEngine & metric computation
│   │   ├── models.py        # BenchmarkCase, GroundTruth, EvaluationRun
│   │   └── storage.py       # Persistence for benchmark cases and runs
│   ├── generator/           # Test synthesis & code generation
│   ├── guardrails/          # SafetyGuardrailEngine & AST code sanitizer
│   ├── llm/
│   │   ├── client.py        # OllamaLLMClient
│   │   └── prompt_manager.py # Prompt techniques
│   ├── rag/
│   │   ├── arbiter.py       # Spec-as-Oracle three-valued arbitration
│   │   ├── deterministic_engine.py # OpenAPI boundary matrix generator
│   │   ├── repo_vector_store.py    # RepoCodeVectorStore (repo_code_store collection)
│   │   ├── semantic_validator.py   # SemanticTestValidator (CodeLlama reasoning)
│   │   └── vector_store.py  # SpecVectorStore (spec_store collection)
│   ├── remediation/         # Autonomous patch synthesis & sandbox verification
│   ├── sourcegraph/
│   │   └── client.py        # SourcegraphClient & LocalCodeGraphFallback
│   ├── web/
│   │   ├── api.py           # FastAPI REST backend
│   │   └── static/          # Single-page dashboard application
│   └── cli.py               # Typer CLI application
├── tests/                   # Comprehensive automated test suite
├── testbed/                 # Controlled target application & OpenAPI spec
└── pyproject.toml           # Project dependencies & build configuration
```

---

## 13. Limitations & Future Work

### Known Architectural Limitations
1. **Dynamic Python Metaprogramming**: Dynamic decorator injections (e.g., Flask `@app.fixture`) are invisible to static AST without runtime execution traces.
2. **Local Fallback vs. Distributed Sourcegraph**: When Sourcegraph server is offline, local AST fallback operates only within the current repository workspace.
3. **Local Embedding Memory**: Sentence-transformers embeddings run on local CPU/Metal memory; massive repositories (&gt;500k LOC) require batch chunking.

### Research Limitations
1. **Quantitative Research Claim Policy**: While Repository RAG and CodeLlama validation are fully implemented and verified, claims of precision/recall improvement over the deterministic baseline require extensive multi-project benchmarking before publication.

### Future Work
1. **Cross-Language Support**: Expanding AST/Tree-sitter symbol extractors to TypeScript, Go, and Rust.
2. **Automated Benchmark Ablation**: Continuous benchmarking of `TestPilot`, `TestPilot + Sourcegraph`, `TestPilot + RAG`, and `TestPilot + Sourcegraph + RAG` across open-source CVE repositories.
