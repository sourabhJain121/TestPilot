# TestPilot AI: Autonomous Spec-as-Oracle Testing and Regression Remediation Agent

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.5%2B-e92063.svg)](https://docs.pydantic.dev)
[![Local LLM](https://img.shields.io/badge/Local_LLM-Ollama_Qwen2.5--Coder-orange.svg)](https://ollama.ai)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Course**: CSE 4011 — Intelligent Developer Tools and AI DevOps Workflows  
> **Role**: Senior Staff Engineer (DevOps & ML Systems) + Capstone Review Panelist  
> **Phase 1 Evaluation (30% Weight)**: Week of September 21, 2026  

---

## 1. The Core Paradigm: Spec-as-Oracle & True Novelty

While schema-conformance and property-based API testing tools like **Schemathesis** and **Specmatic** have long utilized OpenAPI contracts to generate endpoint fuzzing requests, they operate under rigid input-fuzzing assumptions and treat any discrepancy as an undifferentiated failure. Conversely, modern LLM-based test generators frequently treat fallible source code as the oracle, writing assertions that formalize existing software bugs as permanent specification debt.

**TestPilot AI** reframes contract-driven testing by acknowledging prior art in schema conformance while introducing three foundational architectural novelties:

1. **Automated Triaging Arbiter (Three-Valued Logic)**: Rather than reporting binary pass/fail results, TestPilot dynamically retrieves formal specification clauses via semantic RAG and employs three-valued logic (inspired by *AgentAssay*) to distinguish between:
   - `TRUE_CODE_DEFECT`: The code implementation deviates from an unambiguous OpenAPI/PRD specification contract $\rightarrow$ triggers automated remediation.
   - `INVALID_TEST_ASSERTION`: The test hallucinated behavior or asserted ungrounded expectations contradictory to the contract $\rightarrow$ pruned to prevent test debt.
   - `SPEC_AMBIGUITY_OR_DEFECT`: The specification is silent, contradictory, or underspecified on the boundary condition $\rightarrow$ flagged for product/API spec review.
2. **AST-Grounded Boundary Synthesis (Hybrid Deterministic + LLM Engine)**: Combines deterministic OpenAPI schema boundary extraction (numeric extrema, string lengths, enum bounds) and Tree-sitter AST syntax parsing (guard conditions, type annotations) with Chain-of-Thought LLM reasoning over nuanced natural-language PRD requirements.
3. **Closed-Loop Remediation (Sweep.dev Pattern)**: Rather than merely reporting failures, TestPilot autonomously synthesizes code repairs for confirmed `TRUE_CODE_DEFECT` verdicts and executes isolated regression sandboxing (pytest) to validate the patch before generating git PRs.

```
                    ┌──────────────────────────────────────────────┐
                    │   OpenAPI 3.1 & PRD Specification Oracle     │
                    │        (ChromaDB Semantic Retrieval)         │
                    └──────────────────────┬───────────────────────┘
                                           │
                        Three-Valued Arbitration Logic
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌─────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐
│ INVALID_TEST_ASSERTION  │   │     TRUE_CODE_DEFECT      │   │ SPEC_AMBIGUITY_OR_DEFECT  │
│  Prune hallucinated or  │   │ Code violated unambiguous │   │ Specification is silent   │
│   drifted test debt     │   │ contract -> Auto-Remedy   │   │ or ambiguous on boundary  │
└─────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘
```

---

## 2. Strategic Differentiation: TestForge vs. Industry Tools vs. TestPilot AI

| Dimension | Schemathesis / Specmatic | TestForge (Prior Project: CSE 3101) | TestPilot AI (Target Project: CSE 4011) |
| :--- | :--- | :--- | :--- |
| **Core Problem** | Schema validation & fuzzing against HTTP endpoints | Hollow assertions in isolated unit tests | Regression triaging, spec drift, & test debt in CI/CD PRs |
| **Ground Truth Oracle** | Strict OpenAPI Schema alone | **Code is Oracle**: Mutates code to measure test kill rate | **Spec-as-Oracle**: Formal OpenAPI + PRD semantic ground truth |
| **Boundary Analysis** | Black-box property-based fuzzing | Local heuristic mutation analysis | **AST-Grounded Syntax Extrema + Deterministic Schema Matrices + CoT LLM** |
| **Triaging Logic** | Binary (HTTP status / schema validation fail) | Mutation survival binary score | **Three-Valued Arbiter** (`DEFECT` vs `INVALID_TEST` vs `SPEC_AMBIGUITY`) |
| **Remediation** | None (manual engineer debugging) | Retries prompt until mutants die | **Closed-Loop Sandbox Remediation** (Automated Git patch PR) |

---

## 3. End-to-End System Architecture

```mermaid
graph TD
    subgraph Ingestion ["1. Multi-Modal Ingestion & Vector Indexing"]
        Diff["Unified Git Diff / PR"]
        Spec["OpenAPI 3.1 Contract (openapi.json)"]
        PRD["PRD Requirements (Markdown)"]
        Chroma["ChromaDB Vector Store (SentenceTransformers)"]
        Spec --> Chroma
        PRD --> Chroma
    end

    subgraph Intelligence ["2. Code & Graph Intelligence"]
        AST["AST & Unified Diff Parser"]
        SG["Sourcegraph OSS GraphQL Client"]
        Fallback["Autonomous Local AST Call Graph"]
        DetEngine["Deterministic Boundary Extractor (Schema Bounds)"]
    end

    subgraph PromptEngine ["3. Boundary Synthesis Engine"]
        PromptMgr["Prompt Manager (Zero/Few/CoT)"]
        Ollama["Local Ollama (Qwen2.5-Coder:7b)"]
        Validator["Pydantic v2 Schema Validator"]
        Synth["Pytest Code Synthesizer"]
    end

    subgraph Oracle ["4. Three-Valued Arbiter & Closed-Loop Remediation"]
        Runner["Isolated Test Execution (pytest)"]
        Arbiter{"Three-Valued Spec Arbiter"}
        Bug["TRUE_CODE_DEFECT -> Closed-Loop Patch Sandbox"]
        Debt["INVALID_TEST_ASSERTION -> Prune Test Debt"]
        Ambiguity["SPEC_AMBIGUITY_OR_DEFECT -> Flag Spec Debt"]
        PatchBot["Sweep.dev Autonomous Remediation Bot"]
    end

    Diff --> AST
    Diff --> SG
    SG -.->|Docker Offline Fallback| Fallback
    Spec --> DetEngine
    DetEngine --> Synth

    AST --> PromptMgr
    SG --> PromptMgr
    Fallback --> PromptMgr
    Chroma -.->|Retrieved Clauses| PromptMgr

    PromptMgr --> Ollama
    Ollama --> Validator
    Validator --> Synth
    Synth --> Runner

    Runner --> Arbiter
    Chroma -.->|Contract Ground Truth| Arbiter
    Arbiter --> Bug
    Arbiter --> Debt
    Arbiter --> Ambiguity
    Bug --> PatchBot
```

---

## 4. Repository Layout

```
TestPilot/
├── docs/
│   ├── SYNOPSIS.md              # Phase 1 Capstone Charter & Academic Synopsis
│   ├── ARCHITECTURE.md          # Full Architectural Blueprint & Data Contracts
│   └── PHASE1_EVALUATION.md     # Step-by-Step Viva Demonstration Script
├── testbed/                     # Realistic Target Microservice
│   ├── openapi.json             # Exported OpenAPI 3.1 specification
│   └── app/
│       ├── models.py            # Pydantic v2 schemas (CartItem, Order, etc.)
│       ├── services/
│       │   └── order_service.py # Domain logic with 3 intentional boundary bugs
│       └── main.py              # FastAPI REST endpoints + CLI export flag
├── testpilot/                   # TestPilot AI Core Package
│   ├── core/
│   │   └── models.py            # AST, Prompt, and Verdict domain models
│   ├── ast_engine/
│   │   └── treesitter_parser.py # AST parser for unified git diffs & boundary values
│   ├── sourcegraph/
│   │   └── client.py            # GraphQL client with local AST fallback
│   ├── llm/
│   │   ├── client.py            # Ollama client with JSON schema enforcement
│   │   └── prompt_manager.py    # Zero-shot, Few-shot, CoT boundary templates
│   ├── generator/
│   │   └── synthesizer.py       # Syntax-validated Pytest test suite generator
│   └── cli.py                   # Rich terminal CLI
├── docker/
│   └── docker-compose.sourcegraph.yml # Sourcegraph OSS container configuration
├── tests/                       # Test suite
│   ├── test_ast_parser.py       # AST parser and diff chunk tests
│   ├── test_sourcegraph_client.py # GraphQL & local call graph fallback tests
│   ├── test_prompts.py          # Prompt engineering & JSON parsing tests
│   └── test_synthesizer.py      # Pytest synthesis and syntax validation tests
├── pyproject.toml               # Project metadata and CLI script bindings
└── ruff.toml                    # Code style and linting rules
```

---

## 5. Quickstart & Installation

### Prerequisites
- Python 3.10+ (macOS / Linux)
- [Ollama](https://ollama.ai) installed with `qwen2.5-coder:7b`:
  ```bash
  ollama pull qwen2.5-coder:7b
  ```

### Setup Environment
```bash
git clone https://github.com/sourabhJain121/TestPilot.git
cd TestPilot

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and CLI in editable mode
pip install -e .
```

---

## 6. CLI Commands & Evaluation Walkthrough

### 1. System Health Check
Verify Python runtime, local Ollama connectivity, model readiness, and code graph resolution:
```bash
testpilot status
```

### 2. AST Parsing & Boundary Discovery
Inspect decision branch nodes and automatically discovered boundary candidates:
```bash
testpilot parse-diff --file testbed/app/services/order_service.py
```

### 3. Sourcegraph Symbol Navigation & Blast Radius
Query downstream callers using Sourcegraph GraphQL or local AST fallback:
```bash
testpilot check-sourcegraph calculate_order_totals
```

### 4. Synthesize Boundary Tests with Chain-of-Thought
Generate executable `pytest` tests using local `qwen2.5-coder:7b`:
```bash
testpilot generate-tests --file testbed/app/services/order_service.py --technique cot --output tests/generated/test_order_service.py
```

### 5. Execute Spec-as-Oracle Arbitration
Run the generated tests against the testbed microservice and arbitrate the 3 seeded boundary bugs:
```bash
testpilot verify
```

---

## 7. Phase 1 Evaluation Day-by-Day Checklist

- [x] **Day 1**: Monorepo scaffolding with `ruff`, `mypy`, and pytest. Submit the **One-Page Project Charter** (`docs/SYNOPSIS.md`).
- [x] **Day 2**: Deploy modular FastAPI microservice (`testbed/`) with 3 interdependent routes and intentional boundary bugs. Export its `openapi.json`.
- [x] **Day 3**: Launch Sourcegraph via Docker (`sourcegraph/server:5.3.0`). Build the Python client (`sourcegraph/client.py`) to query caller references via GraphQL.
- [x] **Day 4**: Implement resilient fallback: `treesitter_parser.py` extracting AST definitions directly from unified git diffs without external dependencies.
- [x] **Day 5**: Build the Prompt Engine (`prompt_manager.py`) using local Ollama (`qwen2.5-coder:7b`). Implement zero-shot vs. chain-of-thought prompt templates for boundary value discovery.
- [x] **Day 6**: Wire AST diff context into the prompt engine. Validate generated `pytest` code using Pydantic schema constraints.
- [x] **Day 7**: Phase 1 dry run: Demonstrate live Sourcegraph symbol cross-referencing and prompt-driven test generation from the terminal.

---

## 8. Academic Deliverables & Documentation

- [Project Charter & Synopsis](file:///Users/sourabh/TestPilot/docs/SYNOPSIS.md)
- [Architecture Specification](file:///Users/sourabh/TestPilot/docs/ARCHITECTURE.md)
- [Phase 1 Viva & Demo Script](file:///Users/sourabh/TestPilot/docs/PHASE1_EVALUATION.md)
