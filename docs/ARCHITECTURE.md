# TESTPILOT AI: SYSTEM ARCHITECTURE SPECIFICATION
**Course:** CSE 4011: Intelligent Developer Tools and AI DevOps Workflows  
**Document Version:** 1.0.0 (Phase 1 Baseline)  
**Status:** Approved Architectural Blueprint  

---

## 1. System Overview

TestPilot AI is an autonomous, specification-grounded test generation and regression arbitration agent built for modern enterprise CI/CD workflows. It resolves the "Code-as-Oracle" failure mode of standard AI testing tools by anchoring all verification to formal specifications (OpenAPI 3.1 contracts, JSON Schemas, and Product Requirement Documents).

```
+-----------------------------------------------------------------------------------+
|                                  TESTPILOT AI                                     |
+-----------------------------------------------------------------------------------+
|  [Git Diff / PR]   [OpenAPI 3.1 Spec]   [PRD Requirements]                       |
|         │                  │                    │                                 |
|         ▼                  ▼                    ▼                                 |
|  ┌─────────────┐    ┌─────────────┐      ┌─────────────┐                          |
|  │ AST Parser  │    │ Spec Parser │      │ Sourcegraph │ (Downstream blast radius)|
|  └──────┬──────┘    └──────┬──────┘      └──────┬──────┘                          |
|         │                  │                    │                                 |
|         └──────────┬───────┴────────────────────┘                                 |
|                    ▼                                                              |
|        ┌────────────────────────┐                                                 |
|        │  Prompt Engine (CoT)   │ ◄── [Ollama Qwen2.5-Coder:7b]                   |
|        └──────────┬─────────────┘                                                 |
|                    ▼                                                              |
|        ┌────────────────────────┐                                                 |
|        │  Pytest Synthesizer    │                                                 |
|        └──────────┬─────────────┘                                                 |
|                    ▼                                                              |
|        ┌────────────────────────┐                                                 |
|        │ Spec-as-Oracle Arbiter │ ──► [True Defect] ──► Autonomous Patch PR       |
|        └────────────────────────┘ ──► [Test Debt]   ──► Discard & Flag            |
+-----------------------------------------------------------------------------------+
```

---

## 2. Component Specifications

### 2.1 Multi-Modal Ingestion
The ingestion engine extracts structural context from developer changes:
1. **Unified Git Diff**: Ingested via git subprocess or raw diff strings. The diff is mapped to modified line ranges and changed AST nodes.
2. **OpenAPI 3.1 Contract**: Extracted from FastAPI `openapi.json`, parsing route paths, HTTP methods, request body schemas, query parameters, and response status codes with boundary constraints (e.g., `minimum`, `maximum`, `pattern`, `required`).
3. **PRD / Functional Specs**: Markdown-formatted business requirements describing state transition rules, discount policies, and security expectations.

### 2.2 Code Intelligence & Navigation Subsystem
To ensure precise test scoping and understand blast radius:
- **Tree-sitter & Python AST Parser**:
  - Traverses the abstract syntax tree of modified files.
  - Extracts exact function/method signatures, parameter types, default values, docstrings, and return annotations.
  - Identifies conditional branch nodes (`If`, `While`, `Match`, `Try`) to calculate cyclomatic complexity and identify boundary comparison targets (`<`, `<=`, `==`, `!=`, `>=`, `>`).
- **Sourcegraph OSS GraphQL Client**:
  - Queries `http://localhost:7080/.api/graphql` using Sourcegraph's code graph query engine.
  - Identifies all caller references of the modified function across the repository to determine the blast radius.
  - **Graceful Fallback**: If Sourcegraph server is not reachable, TestPilot falls back immediately to a zero-dependency local AST dependency indexer, guaranteeing 100% test and CI pass rates.

### 2.3 Prompt Engineering Subsystem
Test generation uses structured prompting implemented against Ollama (`qwen2.5-coder:7b`):
- **Zero-Shot Strategy**: Standard prompt presenting code signature and docstring.
- **Few-Shot Strategy**: Includes 2-3 canonical exemplars of boundary value tests (null values, maximum integer bounds, empty collections).
- **Chain-of-Thought (CoT) Strategy**: Instructs the model to follow a formal 4-phase reasoning protocol:
  1. *Contract Extraction*: What does the OpenAPI specification mandate?
  2. *Equivalence Partitioning*: What are the valid and invalid input classes?
  3. *Boundary Value Analysis*: What are the exact values on the edges ($0$, $1$, $-1$, empty string, null, max precision)?
  4. *Invariant Verification*: What assertions must hold true across state transitions?
- **Schema Enforcement**: The prompt enforces output strictly adhering to a Pydantic v2 JSON schema (`GeneratedTestSuite`), which is parsed and validated before generating code.

### 2.4 Spec-as-Oracle Arbitration
When synthesized tests run against the target codebase:
- **Case 1: Test Passes**: Code satisfies both developer intent and specification requirements.
- **Case 2: Test Fails & Specification Violated**:
  - The test assertion matches the OpenAPI/PRD rule, but the code produced an illegal output.
  - **Classification**: `TRUE_CODE_DEFECT`.
  - **Action**: Alert CI, mark PR red, trigger autonomous patch generation.
- **Case 3: Test Fails & Specification Satisfied**:
  - The code output adheres to the OpenAPI/PRD rule, but the test asserted an ungrounded or hallucinated expectation.
  - **Classification**: `INVALID_TEST_ASSERTION`.
  - **Action**: Suppress failure, discard test assertion, and log test drift warning.

---

## 3. Data Models & Interface Contracts

```python
class ParameterInfo(BaseModel):
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    is_required: bool = True

class BoundaryCandidate(BaseModel):
    parameter_name: str
    boundary_type: str  # e.g., "zero", "negative", "max_limit", "null", "empty"
    test_value: Any
    rationale: str

class ASTFunctionDef(BaseModel):
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    parameters: list[ParameterInfo]
    return_type: Optional[str] = None
    branch_conditions: list[str] = []
    boundary_candidates: list[BoundaryCandidate] = []

class TestCaseSpec(BaseModel):
    test_name: str
    target_function: str
    boundary_focus: str
    input_payload: dict[str, Any]
    expected_status_or_result: Any
    rationale: str

class GeneratedTestSuite(BaseModel):
    target_module: str
    test_cases: list[TestCaseSpec]
    reasoning_trace: Optional[str] = None
```

---

## 4. Phase 1 Evaluation Checklist
- [x] Monorepo layout initialized with `ruff`, `pyproject.toml`, and virtual environment.
- [x] Project Charter & Synopsis (`docs/SYNOPSIS.md`) detailing the academic scope.
- [x] Target testbed microservice (`testbed/`) with 3 interdependent routes, OpenAPI 3.1 export, and seeded boundary defects.
- [x] Resilient AST diff extractor (`testpilot/ast_engine/treesitter_parser.py`).
- [x] Sourcegraph GraphQL client with local fallback (`testpilot/sourcegraph/client.py`).
- [x] Prompt engine with Zero-shot, Few-shot, and CoT templates (`testpilot/llm/prompt_manager.py`).
- [x] Test synthesizer and Pydantic validator (`testpilot/generator/synthesizer.py`).
- [x] Rich terminal CLI (`testpilot`) with end-to-end dry run capability.
