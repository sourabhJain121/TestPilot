# Project Charter: TestPilot AI

## 1. Problem Statement
Automated unit testing often validates "what the code currently does" rather than "what the specification mandates." This causes subtle regressions, hallucinated assertions, and test drift.

## 2. Core Innovation: Spec-as-Oracle
TestPilot AI grounds test synthesis in API specifications (OpenAPI/Swagger, docstrings, PRDs). When generated tests fail in CI:
- If code contradicts spec: Code defect flagged, fix PR suggested.
- If test contradicts spec: Test marked flaky and regenerated.

## 3. Team Responsibility Matrix
- **Sourabh Jain**: Code Intelligence, Sourcegraph GraphQL Client & Tree-sitter Fallback
- **Shreshth Mittal**: RAG Knowledge Pipeline & OpenAPI Indexing
