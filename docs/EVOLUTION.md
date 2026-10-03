# TestPilot AI: Repository Evolution Intelligence & Event-Based Test Impact Analysis

## 1. Overview

Repository Evolution Intelligence analyzes code modifications across Git revisions, maps transitive blast radiuses across call graphs and event listeners, and prioritizes existing test suites with explainable, evidence-backed rankings.

The event-based impact analyzer addresses indirect couplings where code changes affect event handlers (e.g., listeners registered to framework signals like `post_migrate`, `post_save`, etc.) that are executed dynamically rather than called directly in source code.

---

## 2. Event-Match Classifications

To prevent over-selecting unrelated tests while ensuring affected regression tests are prioritized, TestPilot classifies event-related test matches into four structured categories:

### A. `EXPLICIT_EVENT_DISPATCH`
- **Definition:** The test or its direct execution path contains an explicit, statically identifiable dispatch of the event (e.g., `post_migrate.send(sender=...)`).
- **Interpretation:** Strong evidence that the event lifecycle is executed, but does not guarantee the test exercises the specific changed handler or behavior.
- **Priority Tier:** `MEDIUM` (score `0.70`) unless augmented by behavioral coverage.

### B. `EVENT_TRIGGER_CANDIDATE`
- **Definition:** The test invokes infrastructure that may trigger the event (e.g., `call_command("migrate")`, `MigrationExecutor(...)`, or `executor.migrate(...)`), but lacks behavior-specific assertions or domain coupling.
- **Interpretation:** A possible trigger candidate, not proof of regression coverage. Presented separately to developers as a candidate rather than a high-priority regression test.
- **Priority Tier:** `MEDIUM` (score `0.45`).

### C. `BEHAVIORAL_COVERAGE`
- **Definition:** Concrete, explainable evidence connects the test to the affected behavior. Evidence sources include:
  1. **Domain Model References & Assertions:** The test queries, creates, or asserts against domain entities managed by the handler (e.g., `Permission.objects.filter(...)` for permission renaming).
  2. **Targeted Command Arguments:** The test executes the trigger with arguments targeting the affected app/module (e.g., `call_command("migrate", "auth_tests")`).
  3. **Diff Co-Change Proximity:** The test file was modified or added in the same pull request / commit alongside the changed handler.
  4. **Call Graph Reachability:** The test directly or transitively reaches changed symbols or domain helpers.
- **Interpretation:** High-confidence regression test that demonstrably exercises the changed behavior.
- **Priority Tier:** `HIGH` (score `0.85` - `0.88`).

### D. `NO_RELEVANT_EVENT_EVIDENCE`
- **Definition:** No event dispatch, trigger relationship, or behavioral connection exists.
- **Interpretation:** The test is not impacted by the event change.

---

## 3. Priority Tiering Hierarchy

Priority scores and tiers are determined strictly by evidence:

| Priority Score | Priority Tier | Evidence Criteria | Classification |
|---|---|---|---|
| `0.98` | `CRITICAL` | Direct test of modified Python symbol | `CALL_GRAPH` |
| `0.88` | `HIGH` | Explicit event dispatch (`.send`) + verified domain behavioral coverage | `BEHAVIORAL_COVERAGE` |
| `0.85` | `HIGH` | Candidate trigger (`call_command`) + verified domain behavioral coverage OR local helper call | `BEHAVIORAL_COVERAGE` |
| `0.82` | `HIGH` | Direct caller (1-hop downstream in call graph) | `CALL_GRAPH` |
| `0.70` | `MEDIUM` | Explicit event dispatch without behavioral coverage | `EXPLICIT_EVENT_DISPATCH` |
| `0.60` | `MEDIUM` | Indirect caller (2+ hops downstream in call graph) | `CALL_GRAPH` |
| `0.45` | `MEDIUM` | Heuristic trigger candidate without behavioral coverage | `EVENT_TRIGGER_CANDIDATE` |

---

## 4. Interpreting Output

### CLI (`testpilot evolution`)
- **Evolution Analysis Summary:** Displays `Total Discovered Tests`, `Prioritized Regression Tests` (Critical/High), and `Event-Trigger Candidates`.
- **Prioritized Existing Test Suite Table:** Lists confirmed regression tests with their `Tier`, `Classification`, `Score`, and `Selection Reason / Evidence`.
- **Possible Event-Trigger Candidates Table:** Displays candidates that invoke event triggers with specific `Trigger Evidence` and `Missing Evidence` explanations.

### API (`/api/evolution/analyze`)
- Returns an `EvolutionReport` JSON schema with:
  - `prioritized_tests`: List of confirmed regression tests (`CRITICAL`, `HIGH`, verified `MEDIUM`).
  - `event_trigger_candidates`: List of candidate tests invoking event infrastructure.
  - `total_discovered_tests`: Total count of test items indexed across the repository.
  - Each test item contains `match_classification`, `event_name`, `structured_evidence` (`EvidenceItem[]`), `missing_evidence` (`string[]`), and `selection_reason`.

### Web Dashboard
- **KPI Metrics:** Displays `Event Candidates` card alongside `Prioritized Tests` and `Blast Radius`.
- **Prioritized Regression Tests Panel:** Color-coded classification badges (`BEHAVIORAL COVERAGE`, `EXPLICIT EVENT`), priority score, coverage target, execution command, and uncertainty notices.
- **Event-Trigger Candidates Panel:** Separate section highlighting unconfirmed candidate tests with trigger description and missing evidence.

---

## 5. Running Tests

Run the full Evolution Intelligence test suite:

```bash
# Run all evolution unit and integration tests
pytest tests/test_evolution.py -v

# Run CLI integration tests
pytest tests/test_cli_commands.py -v

# Verify code formatting and linting
ruff check testpilot/ tests/
```

### Running Evaluation Against External Repositories

```bash
testpilot evolution \
  --repo-path "$HOME/testpilot-external-test/django" \
  --base HEAD~1 \
  --target HEAD \
  --max-depth 3
```

---

## 6. Known Limitations

1. **Static Analysis Horizon:** Dynamic signal connection (e.g., runtime `receiver.connect()`) inside dynamically generated functions or eval loops cannot be statically detected without runtime tracing.
2. **Subprocess Invocations:** Tests that run commands in isolated subprocesses (`subprocess.run(["manage.py", "migrate"])`) rather than in-process APIs (`call_command`) are not captured via AST AST-visitor pattern.
3. **Complex Mocking:** Mocks that intercept events dynamically without calling standard dispatch APIs may result in candidates being classified under `EVENT_TRIGGER_CANDIDATE` rather than confirmed dispatch.
