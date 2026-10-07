# 🚀 TestPilot — Evidence-Grounded AI for Change-Aware Regression Testing

### Repository Evolution &rarr; Specification-Grounded Testing &rarr; Three-Valued Failure Arbitration

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Tree-Sitter](https://img.shields.io/badge/AST-Tree--sitter_0.21%2B-5c2d91.svg)](https://tree-sitter.github.io)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.5%2B-e92063.svg)](https://docs.pydantic.dev)
[![Local LLM](https://img.shields.io/badge/Local_LLM-Ollama_CodeLlama_&_Qwen-orange.svg)](https://ollama.ai)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **TestPilot** combines deterministic repository analysis with LLM-based reasoning to identify regression tests affected by code changes, generate specification-grounded boundary tests, and classify failures as code defects, invalid test assertions, or specification ambiguity.

### Research Questions
- **Primary**: *"Can repository-aware AI-assisted impact analysis accurately identify regression tests affected by software changes while reducing unnecessary test execution?"*
- **Secondary**: *"Does combining deterministic repository evidence with LLM-based semantic reasoning improve the reliability of regression-test selection and failure classification compared with simpler baselines?"*

> [!IMPORTANT]
> **Research Positioning**: Autonomous code remediation is an **experimental extension / optional stage**, not the primary validated contribution.
> The primary validated contributions are:
> 1. **Repository-Aware Regression-Test Impact Analysis** (using Git, AST/Tree-sitter, qualified symbol identity, and repository code intelligence).
> 2. **Specification-Grounded Testing** (deterministic OpenAPI boundary extraction coupled with repository context).
> 3. **Three-Valued Failure Arbitration** (`TRUE_CODE_DEFECT`, `INVALID_TEST_ASSERTION`, `SPEC_AMBIGUITY_OR_DEFECT`).
> 4. **Quantitative Evaluation** against established baselines (Full Regression, Naive Name Matching) across real-world repositories (Flask, Django, Home Assistant).

---

## 🌟 Key Research Contributions

1. **Repository-Aware Regression Analysis**:
   - Identifies changed symbols and affected regression tests using Git diffs, AST/Tree-sitter, qualified symbol identity (`SymbolId`), and caller graph traversals.
   - Eliminates generic-token collisions (e.g. constructor `__init__` in Home Assistant) via class and receiver-scoped resolution.

2. **Specification-Grounded Testing**:
   - Extracts deterministic schema boundaries from OpenAPI specifications (e.g. exclusive minimums, enum sets) without stochastic hallucination.

3. **Three-Valued Failure Arbitration**:
   - Classifies failures into `TRUE_CODE_DEFECT`, `INVALID_TEST_ASSERTION`, or `SPEC_AMBIGUITY_OR_DEFECT` using code, test, and specification evidence.

4. **In-App Empirical Evaluation Subsystem**:
   - Traceable, quantitative benchmarking measuring Precision, Recall, F1-Score, Test Reduction %, and Latency against Full Regression and Naive Name Matching baselines.

2. **Repository Evolution Intelligence & Remote Git Testing**:
   - **Direct Git URL Support**: Input any remote Git repository link (e.g., `https://github.com/pallets/flask.git`, `https://github.com/django/django.git`) or local directory. TestPilot shallow-clones (`--depth 50`) into `~/.testpilot_repos/` and analyzes it immediately.
   - **⚡ Zero-Clone In-Memory Public Git Testing**: Test any public GitHub repository or direct file link (e.g., `https://github.com/pallets/flask/blob/main/src/flask/app.py` or `https://github.com/psf/requests/blob/main/src/requests/models.py`) without disk cloning. In-memory HTTP streaming parses AST and generates complete boundary test suites in under 150ms!
   - **AST Symbol Tracking**: Detects added, deleted, and modified Python functions, classes, and methods across commits.
   - **Transitive Blast Radius Call Graph**: Traces direct and indirect callers across the codebase using Sourcegraph GraphQL with local AST fallback.
   - **Explainable Test Prioritization**: Computes uncertainty scores and ranks regression tests into `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW` tiers with token-boundary matching and structured evidence trails.

3. **Multi-Model Local LLM Support (CodeLlama & Qwen)**:
   - Native integration with **Ollama** running locally on your hardware.
   - Supports **CodeLlama** (`codellama:7b`, `codellama:13b`, `codellama:34b`, `codellama:code`) and **Qwen2.5-Coder** (`qwen2.5-coder:7b`).
   - Switch active models dynamically via the UI top bar or CLI environment variables (`OLLAMA_MODEL="codellama:7b"`).

4. **One-Click Downloadable Reports**:
   - **Pipeline Audit Reports**: Export 7-stage Spec-as-Oracle arbitration matrices and sandboxed patches (`.md` / `.json`).
   - **Evolution Intelligence Reports**: Export changed AST symbols, transitive call graphs, and prioritized test suites.
   - **Blast Radius Reports**: Export upstream caller hierarchies, risk assessments, and targeted test command strings directly from Tab 3.
   - Instant browser download or server-side persistence in `reports/`.

5. **Safety Guardrails & AST Quarantine**:
   - Prevents prompt injection, malicious OS system calls (`os.system`, `subprocess.Popen`), unauthorized file deletion (`rm -rf`), and ungrounded hallucinations before any test or patch is executed.

6. **Closed-Loop Sandbox Remediation (Sweep.dev Pattern)**:
   - Synthesizes automated unified git diff patches for confirmed code defects.
   - Automatically validates fixes in an isolated pytest sandbox before creating git branches (`testpilot/fix-*`).

---

## 🏗️ System Architecture

**Repository Evolution Intelligence acts as a change-impact and regression-test-prioritization stage before specification-driven testing.**

The TestPilot pipeline integrates Git code intelligence directly into specification testing and autonomous remediation:

```
Git Change (Diff / Commits / PR)
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [Stage 0] Repository Evolution Intelligence                            │
│  - Changed Python AST Symbols (Functions, Classes, Methods)            │
│  - Transitive Blast Radius (Sourcegraph GraphQL / Local AST Fallback)  │
│  - Prioritized Regression Tests (CRITICAL, HIGH, MEDIUM Tiers)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┴───────────────────────────────┐
    ▼                                                               ▼
┌─────────────────────────────────┐   ┌──────────────────────────────────┐
│ Prioritized Regression Execution│   │ [Stage 1] Deterministic Boundary │
│ (Targeted Impacted Tests First) │   │ Extraction (OpenAPI 3.1 & PRD)   │
└────────────────┬────────────────┘   └─────────────────┬────────────────┘
                 │                                      │
                 └──────────────────┬───────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [Stage 2] Test Synthesis & Execution (Pytest Sandbox)                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [Stage 3] Spec-as-Oracle Triaging Arbiter (Three-Valued Logic)         │
│  - TRUE_CODE_DEFECT: Spec contract violated by code                    │
│  - INVALID_TEST_ASSERTION: Test hallucinated ungrounded assertion     │
│  - SPEC_AMBIGUITY_OR_DEFECT: Specification underspecified / flawed     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [Stage 4] Safety Guardrails & AST Quarantine                           │
│  - Prompt Injection Defense, Syscall Blocker, Hallucination Gate       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ [Stage 5] Autonomous Remediation & Sandbox Verification                │
│  - Unified Diff Generation & Isolated Pytest Sandbox Patch Validation  │
└────────────────────────────────────────────────────────────────────────┘
```

### 🛡️ Graceful Degradation
If Git refs cannot be resolved, the repository path is missing/unsupported, or Sourcegraph is offline:
- Evolution analysis gracefully marks its status as `DEGRADED` with a clear warning.
- The pipeline proceeds directly to specification and boundary testing without crashing.
- Sourcegraph falls back automatically to local AST call-graph indexing.
- Zero impacted tests are reported cleanly without fabricating fake blast radius.

---

## 📋 Prerequisites & Installation

### 1. System Requirements
- **macOS** (Apple Silicon M-series recommended) or **Linux** (x86_64 / aarch64)
- **Python**: `>= 3.10` (Tested on Python 3.11, 3.12, 3.14)
- **Git**: `>= 2.30`
- **Ollama**: Local LLM runner ([Download Ollama](https://ollama.ai))

### 2. Install Ollama & Models
Start the Ollama background service and pull the recommended coding models:

```bash
# Pull CodeLlama 7B (Default)
ollama pull codellama:7b

# (Optional) Pull Qwen2.5-Coder
ollama pull qwen2.5-coder:7b

# Verify models are installed
ollama list
```

### 3. Clone and Setup TestPilot
```bash
# Clone the TestPilot repository
git clone https://github.com/sourabhJain121/TestPilot.git
cd TestPilot

# Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## 🚀 Running TestPilot

### Option A: Launch the Interactive Web Dashboard (Recommended)

Run TestPilot with the **CodeLlama** model:

```bash
# Start Web UI with CodeLlama 7B on port 8501
OLLAMA_MODEL="codellama:7b" testpilot ui --port 8501 --host 127.0.0.1
```

Or run with **Qwen2.5-Coder**:
```bash
OLLAMA_MODEL="qwen2.5-coder:7b" testpilot ui --port 8501 --host 127.0.0.1
```

Once launched, open your web browser at:
👉 **[http://127.0.0.1:8501](http://127.0.0.1:8501)**

---

### Option B: CLI Commands

#### 1. Run Full End-to-End Pipeline (Integrated Evolution + Boundaries + Arbiter + Remediation)
```bash
# Execute the full 6-stage pipeline on the local repo or cloned repository:
testpilot pipeline --repo-path . --base HEAD~1 --target HEAD

# Or execute with custom Git refs:
testpilot pipeline --repo-path ~/.testpilot_repos/core --base HEAD~1 --target HEAD
```

#### 2. Standalone Repository Evolution Intelligence
```bash
# Analyze changes between two commits in the current repo:
testpilot evolution analyze --base HEAD~1 --target HEAD --repo-path .

# Analyze a specific remote or cloned repository:
testpilot evolution analyze --base main~5 --target main --repo-path ~/.testpilot_repos/flask
```

#### 2. Deterministic Schema Boundary Test Generation
```bash
# Generate deterministic boundary tests for OrderRequest schema
testpilot testgen generate --schema OrderRequest --boundary all --out tests/generated/test_order_service.py
```

#### 3. Spec-as-Oracle Arbitration
```bash
# Arbitrate failures in the testbed microservice against PRD / OpenAPI specs
testpilot testgen arbitrate --test-path tests/generated/test_order_service.py
```

#### 4. Autonomous Code Remediation
```bash
# Synthesize an isolated patch for a true code defect
testpilot remediate --file testbed/app/services/order_service.py --out remediation.patch
```

---

## 🖥️ Web Dashboard Tour: Step-by-Step Verification

The TestPilot web interface (`http://127.0.0.1:8501`) provides 9 integrated modules:

| Tab Name | Description | Key User Action |
|:---|:---|:---|
| **1. Overview** | System health, Ollama status, active model, and telemetry. | View live connected models, active vector store, and guardrails. |
| **2. Target Git Repo & Evolution** | Git diff analysis & Zero-Clone in-memory test synthesis. | (A) Input git URL, click **Load / Clone Repo**, and click **Analyze Evolution**; OR (B) paste public GitHub file, click **Fetch & Synthesize Tests (Zero-Clone)**. |
| **3. AST Diff Inspector** | Tree-sitter semantic function change parser. | Compare old vs new Python code to view added/modified methods and parameters. |
| **4. Transitive Blast Radius** | Sourcegraph GraphQL / Local AST caller graph traversal. | Enter symbol (e.g. `calculate_order_totals`), click **Resolve Callers**, and click **Download Blast Report**. |
| **5. Deterministic Boundaries** | High-precision boundary matrix generator. | Select schema `OrderRequest` and click **Generate Boundary Suite**. |
| **6. Spec Triaging Arbiter** | Three-valued logic contract arbitration. | Click **Arbitrate Failures** to see `TRUE_CODE_DEFECT`, `INVALID_TEST_ASSERTION`, `SPEC_AMBIGUITY_OR_DEFECT`. |
| **7. Safety Guardrails** | AST code quarantine & injection defense. | Test malicious scripts (`os.system('rm -rf /')`) to verify quarantine defense. |
| **8. Autonomous Remediation** | Sweep.dev pattern automated patch generation. | Click **Generate & Verify Patch** to synthesize and sandbox a verified fix. |
| **9. Empirical Benchmarks** | Comparative metrics across models and tools. | Compare CodeLlama vs Qwen vs Schemathesis across precision and recall. |

---

## 📥 Downloadable Reports

TestPilot generates clean, publication-ready reports in both Markdown and JSON:

1. **Evolution Tab Button (`Download Report`)**:
   - Instantly exports the Repository Evolution Intelligence Report with changed AST symbols, transitive call paths, uncertainty scores, and executable regression test commands.
2. **Blast Radius Tab Button (`Download Blast Report`)**:
   - Instantly exports the Transitive Blast Radius Report with target symbol callers, upstream hierarchy tables, risk scoring, and targeted test command strings (`pytest -k "..."`).
3. **Zero-Clone Suite Download (`Download .py Suite`)**:
   - Instantly exports the synthesized Python boundary test suite generated directly from the public GitHub repository without disk cloning.
4. **Persisted Disk Storage**:
   - All exported reports are automatically archived under the `reports/` directory with UTC timestamps.

---

## 🧪 Running Automated Tests & Linting

TestPilot includes a comprehensive test suite (117+ tests) with zero-tolerance strict linting:

```bash
# Run the focused evolution intelligence test suite
.venv/bin/pytest tests/test_evolution.py -v

# Run the complete test suite
.venv/bin/pytest -v

# Run Ruff code analysis
.venv/bin/ruff check testpilot/ tests/
```

---

## 📂 Project Directory Structure

```
TestPilot/
├── testpilot/
│   ├── ast_engine/             # Tree-sitter AST syntax and diff parsers
│   ├── evolution/              # Repository Evolution Intelligence & Git analysis
│   │   ├── engine.py           # Core diff, symbol change, and test prioritization
│   │   ├── models.py           # Pydantic schemas for impact nodes and reports
│   │   └── evaluator.py        # Empirical precision/recall benchmark engine
│   ├── guardrails/             # AST code quarantine & anti-injection guardrails
│   ├── llm/                    # Ollama client supporting CodeLlama & Qwen
│   ├── rag/                    # Vector store, ChromaDB, and 3-Valued Arbiter
│   ├── remediation/            # Sweep.dev pattern autonomous patch generator
│   ├── sourcegraph/            # Sourcegraph GraphQL client with local fallback
│   └── web/                    # FastAPI backend and responsive Glassmorphism UI
│       ├── api.py              # REST API endpoints (load repo, model switch, export)
│       └── static/index.html   # Single-page modern developer dashboard
├── testbed/                    # Isolated microservice with seeded business bugs
├── tests/                      # Full pytest verification suite
│   ├── test_evolution.py       # 28 comprehensive evolution regression tests
│   └── test_deterministic_engine.py
├── reports/                    # Persisted audit and benchmark reports
├── docs/                       # Architecture and evolution specifications
├── pyproject.toml              # Build configuration and project dependencies
└── README.md                   # Complete documentation
```

---

## 👥 Authors & Academic Context

- **Author**: Sourabh Jain
- **Repository**: [sourabhJain121/TestPilot](https://github.com/sourabhJain121/TestPilot)
- **License**: MIT
