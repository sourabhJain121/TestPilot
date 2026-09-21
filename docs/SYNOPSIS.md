# CAPSTONE PROJECT SYNOPSIS & CHARTER: TESTPILOT AI
**Course Code:** CSE 4011 — Intelligent Developer Tools and AI DevOps Workflows  
**Academic Year:** 2026–2027  
**Project Title:** TestPilot AI: Autonomous Spec-as-Oracle Testing and Regression Remediation Agent for CI/CD  
**Project Track:** AI-Driven DevOps / Developer Productivity Tools  
**Evaluation Phase:** Phase 1 (30% Evaluation — Week of September 21, 2026)  

---

## 1. Executive Summary & Problem Definition

In modern continuous integration and delivery (CI/CD) pipelines, automated testing is the primary gatekeeper for software reliability. While schema-conformance and property-based fuzzing tools like **Schemathesis** and **Specmatic** have established the practice of testing endpoints against OpenAPI specifications, they treat any schema-request mismatch as an undifferentiated failure and do not analyze code ASTs or arbitrate why a test failed. Conversely, emerging LLM-based test generators frequently treat fallible source code as the oracle, encoding bugs into test assertions and creating persistent test debt.

TestPilot AI does not claim that utilizing specifications as an oracle is inherently new; rather, TestPilot's true novelty lies in three core technical contributions:
1. **Automated Triaging Arbiter (Three-Valued Logic)**: Directly addresses the triaging friction between code defects and bad tests by implementing three-valued logic (inspired by *AgentAssay*) to classify execution failures into `TRUE_CODE_DEFECT`, `INVALID_TEST_ASSERTION`, or `SPEC_AMBIGUITY_OR_DEFECT` via ChromaDB semantic vector retrieval and local LLM reasoning.
2. **AST-Grounded Boundary Synthesis**: Combines deterministic OpenAPI schema boundary extraction (numeric extrema, string lengths, enum bounds) with syntax-level AST code intelligence (branch conditionals, parameter bounds) and Chain-of-Thought LLM reasoning over complex PRD business logic.
3. **Closed-Loop Remediation**: Validated automated patch generation via regression sandboxing (pytest) before generating branch/PR artifacts (Sweep.dev pattern).

---

## 2. Strategic Differentiation: Industry Tools vs. TestForge vs. TestPilot AI

To maintain clear academic rigor and prevent project overlap, TestPilot AI establishes a distinct architectural boundary from prior unit-level mutation testing systems (such as TestForge) and industry schema fuzzers (such as Schemathesis and Specmatic):

| Dimension | Schemathesis / Specmatic | TestForge (Prior Project: CSE 3101) | TestPilot AI (This Project: CSE 4011) |
| :--- | :--- | :--- | :--- |
| **Core Problem** | API schema validation & black-box fuzzing | Eliminating hollow tests with low mutation kill rates | Regression triaging, spec drift, & test debt in CI/CD PRs |
| **Ground Truth / Oracle** | Strict OpenAPI Schema alone | **Code is Oracle**: Mutates source code to check test sensitivity | **Spec-as-Oracle**: Formal OpenAPI contracts + PRD semantic constraints |
| **Execution Domain** | CLI HTTP endpoint fuzzing runner | Local interactive workstation (Streamlit UI) | **Headless Production CI/CD Pipeline** (Rich Typer CLI + GitHub Actions) |
| **Scope of Intelligence** | HTTP boundary payloads (no AST) | Single isolated Python file/module | **Repository-Wide Code Graph** (Sourcegraph AST + blast radius + schema bounds) |
| **Core AI Architecture** | Hypothesis property-based generation | Local MLX GPU Multi-Layer Perceptron Classifier | **Hybrid Deterministic Schema Extractor + Prompt Harness (Zero/Few/CoT)** + Ollama |
| **Failure Resolution** | Raw HTTP failure traceback | Regenerates test assertions until mutants die | **Three-Valued Arbiter** (`DEFECT`, `INVALID_TEST`, `SPEC_AMBIGUITY`) + Auto-Patch PRs |

---

## 3. System Architecture & Core Modules

TestPilot AI consists of four decoupled subsystems designed for enterprise CI/CD integration:

1. **Multi-Modal Ingestion & Vector Indexing Engine**: Ingests unified `git diff` patches, OpenAPI 3.1 JSON/YAML schemas, and natural-language PRD specifications into a persistent ChromaDB vector store with SentenceTransformer embeddings.
2. **Code & Graph Intelligence Layer**:
   - **Deterministic Boundary Extractor**: Parses OpenAPI 3.0/3.1 schemas directly for numeric and string constraints (`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `minLength`, `maxLength`, `enum`) and synthesizes deterministic boundary test matrices without LLM overhead.
   - **Sourcegraph OSS Client**: Interfaces with Sourcegraph GraphQL API to extract reference hierarchies and downstream callers of modified functions.
   - **Resilient AST Fallback**: Native Python AST parser extracting function definitions, parameter constraints, and branch conditions offline.
3. **Prompt Engineering & Synthesis Engine**:
   - Executes systematic prompt techniques: Zero-shot, Few-shot, and **Chain-of-Thought (CoT)** targeting Boundary Value Analysis (BVA).
   - Generates structured, schema-compliant JSON payloads validated via Pydantic v2 schemas.
   - Synthesizes clean, executable `pytest` test suites.
4. **Three-Valued Spec Arbiter & Closed-Loop Remediation Sandbox**:
   - Executes synthesized tests in an isolated sandbox.
   - Evaluates test failures against retrieved specification clauses with a three-valued logic system: `TRUE_CODE_DEFECT`, `INVALID_TEST_ASSERTION`, or `SPEC_AMBIGUITY_OR_DEFECT`.
   - Synthesizes and sandbox-validates automated code patches for confirmed code defects before emitting unified diff PR patches.

---

## 4. 7-Day Sprint Plan & Phase 1 Milestones

| Timeline | Milestone | Key Deliverables | Rubric Alignment |
| :--- | :--- | :--- | :--- |
| **Day 1** | Monorepo Scaffolding & Charter | Project structure, `pyproject.toml`, `ruff`, Charter submission | Problem Definition (5%) |
| **Day 2** | Target Testbed Microservice | Modular FastAPI e-commerce app (`testbed/`) with 3 routes, seeded boundary bugs, exported `openapi.json` | Tool Configuration (5%) |
| **Day 3** | Sourcegraph OSS Setup | Docker Compose configuration, GraphQL client (`sourcegraph/client.py`) querying symbols and caller references | Sourcegraph Setup (10%) |
| **Day 4** | AST Parser & Tree-sitter Fallback | Zero-dependency AST diff parser extracting signatures, types, and branch conditions (`ast_engine/treesitter_parser.py`) | Semantic Navigation (5%) |
| **Day 5** | Prompt Engine & Local Ollama | Unified LLM client (`llm/client.py`) with `qwen2.5-coder:7b`, Zero-shot / Few-shot / CoT prompt templates | Prompt Engineering (5%) |
| **Day 6** | Schema Validation & Synthesizer | Pydantic v2 structured output validation and pytest synthesizer targeting boundary conditions | Test Synthesis (5%) |
| **Day 7** | CLI Integration & Phase 1 Dry-Run | Rich Typer CLI (`testpilot`), testbed bug isolation verification, evaluation walkthrough script | Live Viva & Demo (10%) |

---

## 5. Team Responsibilities & Ownership Matrix

| Member | Primary Responsibility | Subsystem Ownership |
| :--- | :--- | :--- |
| **Sourabh Jain (Lead)** | System Architecture & Core Orchestration | CLI, Spec-as-Oracle Arbiter, LLM Client Integration |
| **Member 2** | Code Intelligence & Graph Navigation | Sourcegraph GraphQL Client & Tree-sitter AST Diff Extractor |
| **Member 3** | Target Testbed & Contract Modeling | FastAPI E-Commerce Microservice & OpenAPI 3.1 Schema Export |
| **Member 4** | Prompt Engineering & Test Synthesis | Zero-shot / Few-shot / CoT Templates & Pydantic Validation |

---

## 6. Phase 1 Evaluation Criteria & Expected Outcomes

By the completion of Phase 1, the TestPilot AI system will demonstrate:
1. An operational repository adhering to enterprise code quality standards (`ruff`, `mypy`, `pytest`).
2. A working FastAPI testbed microservice with verified OpenAPI 3.1 specification contracts and seeded boundary defects.
3. Automated extraction of modified functions and boundary parameters from git diffs using the AST engine.
4. Live caller reference queries against Sourcegraph OSS with graceful offline local fallback.
5. Local LLM test generation using `qwen2.5-coder:7b` with Chain-of-Thought boundary analysis yielding executable, passing/failing pytest tests that isolate the testbed bugs.
