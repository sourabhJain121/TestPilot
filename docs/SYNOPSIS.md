# CAPSTONE PROJECT SYNOPSIS & CHARTER: TESTPILOT AI
**Course Code:** CSE 4011 — Intelligent Developer Tools and AI DevOps Workflows  
**Academic Year:** 2026–2027  
**Project Title:** TestPilot AI: Autonomous Spec-as-Oracle Testing and Regression Remediation Agent for CI/CD  
**Project Track:** AI-Driven DevOps / Developer Productivity Tools  
**Evaluation Phase:** Phase 1 (30% Evaluation — Week of September 21, 2026)  

---

## 1. Executive Summary & Problem Definition

In modern continuous integration and delivery (CI/CD) pipelines, automated testing is the primary gatekeeper for software reliability. However, developer velocity is severely impeded by three critical limitations in current AI and heuristic testing tools:

1. **Hallucinated Assertions & Test Debt**: Existing LLM test generators treat existing source code as the ground truth. When source code contains subtle boundary defects or logic regressions, the LLM faithfully encodes the buggy behavior into test assertions, effectively formalizing code defects as expected behavior.
2. **Specification Drift**: Software contracts (OpenAPI 3.1 specifications, PRD documentation, API schemas) rapidly diverge from implementation code over successive pull requests. Current CI/CD systems lack semantic cross-verification between code diffs and formal contracts.
3. **Triaging Friction (Bug vs. Bad Test)**: When a CI test fails, engineers spend hours diagnosing whether the test was flaky/drifted or if a genuine production regression occurred.

**TestPilot AI** solves this by pioneering the **Spec-as-Oracle** paradigm. By combining multi-modal code intelligence (Tree-sitter AST parsing, Sourcegraph code graphs, and OpenAPI contract embeddings), TestPilot AI treats formal specifications as the ground truth oracle to automatically synthesize boundary-hardened test suites, arbitrate failure causes, and auto-generate remediation pull requests.

---

## 2. Strategic Differentiation: TestForge vs. TestPilot AI

To maintain clear academic rigor and prevent project overlap, TestPilot AI establishes a distinct architectural boundary from prior unit-level mutation testing systems (such as TestForge):

| Dimension | TestForge (Prior Project: CSE 3101) | TestPilot AI (This Project: CSE 4011) |
| :--- | :--- | :--- |
| **Core Problem** | Eliminating hollow tests with low mutation kill rates | Specification drift and regressions in CI/CD PRs |
| **Ground Truth / Oracle** | **Code is Oracle**: Mutates source code to check test sensitivity | **Spec is Oracle**: Code is fallible; OpenAPI/PRD acts as ground truth |
| **Execution Domain** | Local interactive workstation (Streamlit UI) | **Headless Production CI/CD Pipeline** (CLI + GitHub Actions) |
| **Scope of Intelligence** | Single isolated Python file/module | **Repository-Wide Code Graph** (Sourcegraph AST + blast radius) |
| **Core AI Architecture** | Local MLX GPU Multi-Layer Perceptron Classifier | **Prompt Harness & Spec RAG** (Ollama Qwen2.5-Coder + LangChain) |
| **Failure Resolution** | Regenerates test assertions until mutants die | **Arbitrates Defect vs. Test Debt** and proposes code fix PRs |

---

## 3. System Architecture & Core Modules

TestPilot AI consists of four decoupled subsystems designed for enterprise CI/CD integration:

1. **Multi-Modal Ingestion Engine**: Ingests unified `git diff` patches, OpenAPI 3.1 JSON/YAML schemas, and natural-language PRD specifications.
2. **Code & Graph Intelligence Layer**:
   - **Sourcegraph OSS Client**: Interfaces with Sourcegraph GraphQL API (`http://localhost:7080/.api/graphql`) to extract reference hierarchies and downstream callers of modified functions.
   - **Resilient AST Fallback**: Native Python AST / Tree-sitter extractor parsing function definitions, parameter constraints, and branch conditions offline without requiring persistent container services.
3. **Prompt Engineering & Synthesis Engine**:
   - Executes systematic prompt techniques: Zero-shot, Few-shot, and **Chain-of-Thought (CoT)** targeting Boundary Value Analysis (BVA).
   - Generates structured, schema-compliant JSON payloads validated via Pydantic v2 schemas.
   - Synthesizes clean, executable `pytest` test suites.
4. **Spec-as-Oracle Arbiter & Auto-Remediation Sandbox**:
   - Executes synthesized tests in an isolated sandbox.
   - Compares test failures against OpenAPI schema rules.
   - Classifies failures into **True Code Defect** (PR violates spec) or **Invalid Test Assertion** (test contradicts spec).

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
