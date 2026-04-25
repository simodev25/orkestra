---
id: chg-BUG-3-test-plan
status: Proposed
created: 2026-04-25T12:29:28Z
last_updated: 2026-04-25T12:29:28Z
owners:
  - mbensass
service: agent-factory
labels:
  - security
  - enforcement
  - agent-factory
  - forbidden-effects
links:
  change_spec: doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/chg-BUG-3-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: patch
summary: >-
  Validate BUG-3 fix: enforce agent forbidden_effects unconditionally, preserve Test Lab audit (MCPInvocation + mcp.denied), add non-Test-Lab WARNING logging, and remove dead guarded_mcp_executor module.
---

# Test Plan - Forbidden Effects Enforcement Bypassed Outside Test Lab

## 1. Scope and Objectives

**In scope** (from change spec):

- Unconditional enforcement of `forbidden_effects` during agent construction (F-1) across all execution contexts.
- Context-aware audit behavior (F-2):
  - Test Lab context (`test_run_id` + `db`): preserve existing persistence + event emission (DM-1, EVT-1).
  - Non-Test-Lab context: emit structured WARNING log entries (EVT-2) and do not create DB audit records.
- Removal of dead enforcement module `guarded_mcp_executor.py` (F-3).

**Objectives**:

- Provide regression coverage for the bypass bug (AC-F1-1).
- Prevent regressions for agents without `forbidden_effects` (AC-F1-3).
- Validate observability and data-integrity requirements for non-Test-Lab enforcement (AC-F2-1, AC-F2-2).
- Ensure the Test Lab audit trail remains intact (AC-F1-2).
- Ensure dead code is removed and not referenced (AC-F3-1).

## 2. References

- Change spec: `doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/chg-BUG-3-spec.md`
- Testing strategy: `.ai/rules/testing-strategy.md`
- (No implementation plan file present for BUG-3 at time of writing.)

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| ID | Requirement | Coverage | Test Scenario(s) |
|---|---|---|---|
| F-1 | Unconditional forbidden-effects enforcement at agent construction | Covered | TC-FORBIDDEN-001, TC-FORBIDDEN-002, TC-FORBIDDEN-003 |
| F-2 | Context-aware audit trail (Test Lab audit preserved; non-Test-Lab warning logs; no orphan DB records) | Covered | TC-FORBIDDEN-002, TC-FORBIDDEN-004, TC-FORBIDDEN-005 |
| F-3 | Removal of dead enforcement module | Covered | TC-FORBIDDEN-006 |
| AC-F1-1 | Enforcement fires without `test_run_id` (regression) | Covered | TC-FORBIDDEN-001 |
| AC-F1-2 | Test Lab path preserved (tool excluded + MCPInvocation + mcp.denied) | Covered | TC-FORBIDDEN-002 |
| AC-F1-3 | Agents without `forbidden_effects` unaffected | Covered | TC-FORBIDDEN-003 |
| AC-F2-1 | WARNING log emitted per excluded tool in non-Test-Lab context | Covered | TC-FORBIDDEN-004 |
| AC-F2-2 | No MCPInvocation created outside Test Lab | Covered | TC-FORBIDDEN-005 |
| AC-F3-1 | `guarded_mcp_executor.py` absent and unreferenced | Covered | TC-FORBIDDEN-006 |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| ID | Interface | Coverage | Test Scenario(s) |
|---|---|---|---|
| EVT-1 | `mcp.denied` event (Test Lab) | Covered | TC-FORBIDDEN-002 |
| EVT-2 | Structured WARNING log (non-Test-Lab) | Covered | TC-FORBIDDEN-004 |
| DM-1 | `MCPInvocation` persistence (Test Lab only; no schema change) | Covered | TC-FORBIDDEN-002, TC-FORBIDDEN-005 |

### 3.3 Non-Functional Coverage (NFR-#)

| ID | NFR | Coverage | Test Scenario(s) |
|---|---|---|---|
| NFR-1 | Correctness: matching tools excluded regardless of `test_run_id` when `forbidden_effects` non-empty | Covered | TC-FORBIDDEN-001, TC-FORBIDDEN-002 |
| NFR-2 | Performance: p99 construction latency increase ≤ 5 ms | Planned / Manual | TC-FORBIDDEN-007 |
| NFR-3 | Observability: exactly one WARNING log per excluded tool (non-Test-Lab) | Covered | TC-FORBIDDEN-004 |
| NFR-4 | Data integrity: no MCPInvocation without valid `test_run_id` | Covered | TC-FORBIDDEN-005 |
| NFR-5 | Maintainability: single enforcement location; dead module removed | Covered | TC-FORBIDDEN-006 |
| NFR-6 | Test coverage: unit tests cover (a) no `test_run_id`, (b) with `test_run_id`, (c) empty `forbidden_effects` | Covered | TC-FORBIDDEN-001, TC-FORBIDDEN-002, TC-FORBIDDEN-003 |
| AC-NFR-2-1 | Performance acceptance: p99 increase ≤ 5 ms vs baseline | Planned / Manual | TC-FORBIDDEN-007 |

## 4. Test Types and Layers

Aligned with `.ai/rules/testing-strategy.md`:

- **Unit / service-level tests (pytest)** are the primary layer for this change, validating agent construction outcomes and branching audit behavior.
- **Integration-style tests (pytest + in-memory SQLite)** are used where DB persistence is required (MCPInvocation) (Test Lab path).
- **No external services**: MCP calls/events are asserted via mocks/spies; DB uses SQLite in-memory.

Planned locations (convention-based; final file names should follow the repository’s existing naming patterns):

- `tests/test_agent_factory.py` (or module-matching equivalent) — enforcement and logging behavior.
- `tests/services/test_test_lab_audit.py` (or module-matching equivalent) — Test Lab persistence + event emission assertions.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC-ID | Title | Type(s) | Automation | Priority | Related IDs |
|---|---|---|---|---|---|
| TC-FORBIDDEN-001 | Enforce forbidden effects without test_run_id (regression) | Unit | Automated | High | F-1, AC-F1-1, NFR-1, NFR-6 |
| TC-FORBIDDEN-002 | Preserve Test Lab audit path (tool excluded + MCPInvocation + mcp.denied) | Integration | Automated | High | F-1, F-2, AC-F1-2, EVT-1, DM-1 |
| TC-FORBIDDEN-003 | Agents without forbidden_effects unchanged (with and without test_run_id) | Unit | Automated | High | F-1, AC-F1-3, NFR-6 |
| TC-FORBIDDEN-004 | Non-Test-Lab enforcement emits exactly one WARNING per excluded tool | Unit | Automated | High | F-2, AC-F2-1, EVT-2, NFR-3 |
| TC-FORBIDDEN-005 | Non-Test-Lab enforcement creates no MCPInvocation records | Integration | Automated | High | F-2, AC-F2-2, DM-1, NFR-4 |
| TC-FORBIDDEN-006 | guarded_mcp_executor removed and unreferenced | Manual | Manual | Medium | F-3, AC-F3-1, NFR-5 |
| TC-FORBIDDEN-007 | Agent construction performance: p99 delta ≤ 5 ms | Performance | Semi-automated | Low | NFR-2, AC-NFR-2-1 |

### 5.2 Scenario Details

#### TC-FORBIDDEN-001 - Enforce forbidden effects without test_run_id (regression)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-1, NFR-1, NFR-6
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/test_agent_factory.py`
**Tags**: @backend

**Preconditions**:

- An agent definition exists with `forbidden_effects` including at least `"write"`.
- A tool set is available that includes:
  - at least one tool that the current `EffectClassifier` classifies as `"write"`, and
  - at least one tool that is not classified as `"write"` (control tool).

**Steps**:

1. Call `create_agentscope_agent(agent_def, tools=..., db=<any or None>, test_run_id=None)`.
2. Inspect the constructed agent’s registered toolkit / tool registry.

**Expected Outcome**:

- All tools classified under the `"write"` effect are absent from the registered toolkit.
- Control (non-write) tools remain present.

**Notes / Clarifications** (optional):

- This explicitly covers the bug regression where enforcement was previously gated on `test_run_id`.

#### TC-FORBIDDEN-002 - Preserve Test Lab audit path (tool excluded + MCPInvocation + mcp.denied)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, F-2, AC-F1-2, EVT-1, DM-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_test_lab_audit.py` (or equivalent service-level integration test file)
**Tags**: @backend

**Preconditions**:

- In-memory SQLite DB is available via standard pytest fixtures (`AsyncSession`).
- A valid `test_run_id` value is available.
- An agent definition exists with `forbidden_effects=["write"]`.
- A tool set exists containing at least one tool classified as `"write"`.
- The mechanism used by Test Lab to emit `mcp.denied` can be observed (e.g., spy/mocked emitter).

**Steps**:

1. Call `create_agentscope_agent(agent_def, tools=..., db=<AsyncSession>, test_run_id=<run_id>)`.
2. Inspect the agent toolkit to confirm excluded tools.
3. Query the DB for the persisted `MCPInvocation` record(s) associated with the denied tool(s) and `test_run_id`.
4. Verify an `mcp.denied` event was emitted for each denied tool according to existing Test Lab behavior.

**Expected Outcome**:

- Denied `"write"` tools are absent from the toolkit.
- An `MCPInvocation` record is persisted for each denied tool (unchanged Test Lab audit trail).
- An `mcp.denied` event is emitted (unchanged behavior).

#### TC-FORBIDDEN-003 - Agents without forbidden_effects unchanged (with and without test_run_id)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-1, AC-F1-3, NFR-6
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/test_agent_factory.py`
**Tags**: @backend

**Preconditions**:

- An agent definition exists with `forbidden_effects` empty or null.
- A tool set exists containing at least one tool that would normally be classified as `"write"`.

**Steps**:

1. Call `create_agentscope_agent(agent_def, tools=..., test_run_id=None)`.
2. Call `create_agentscope_agent(agent_def, tools=..., test_run_id=<run_id>, db=<db or None>)`.
3. Compare toolkits from both agents.

**Expected Outcome**:

- In both calls, the agent toolkit is unmodified: all tools are present.
- No denied-tool audit side effects occur.

#### TC-FORBIDDEN-004 - Non-Test-Lab enforcement emits exactly one WARNING per excluded tool

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-2, AC-F2-1, EVT-2, NFR-3
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/test_agent_factory.py`
**Tags**: @backend

**Preconditions**:

- Logging capture is available (e.g., pytest `caplog`).
- An agent definition exists with `forbidden_effects` containing at least one category (e.g., `"write"`).
- A tool set exists containing two or more tools that classify into the forbidden category (to validate “per excluded tool”).
- Construction context is non-Test-Lab: `test_run_id=None`.

**Steps**:

1. Call `create_agentscope_agent(...)` without `test_run_id`.
2. Capture WARNING logs emitted during construction.
3. For each excluded tool, locate the corresponding log entry.

**Expected Outcome**:

- Exactly one WARNING log entry exists per excluded tool during construction.
- Each WARNING entry includes (at minimum) the structured fields required by spec: `agent_id`, `tool_name`, `forbidden_effect`, and a context indicator.

#### TC-FORBIDDEN-005 - Non-Test-Lab enforcement creates no MCPInvocation records

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, AC-F2-2, DM-1, NFR-4
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/services/test_test_lab_audit.py` (or equivalent integration test file)
**Tags**: @backend

**Preconditions**:

- In-memory SQLite DB is available via standard pytest fixtures (`AsyncSession`).
- An agent definition exists with `forbidden_effects=["write"]`.
- A tool set exists containing at least one tool classified as `"write"`.
- Construction context is non-Test-Lab: `test_run_id=None`.

**Steps**:

1. Call `create_agentscope_agent(agent_def, tools=..., db=<AsyncSession>, test_run_id=None)`.
2. Query the DB for any newly created `MCPInvocation` records produced by this action.

**Expected Outcome**:

- Denied tools are excluded from the agent toolkit.
- Zero `MCPInvocation` records are created (no orphan records without `test_run_id`).

#### TC-FORBIDDEN-006 - guarded_mcp_executor removed and unreferenced

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-3, AC-F3-1, NFR-5
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Repository-wide check (code search)
**Tags**: @backend

**Preconditions**:

- The BUG-3 change is applied in the working tree.

**Steps**:

1. Verify the file `guarded_mcp_executor.py` does not exist in the repository.
2. Verify no imports or references to `guarded_mcp_executor` remain.

**Expected Outcome**:

- No `guarded_mcp_executor.py` file exists.
- No code references or imports reference `guarded_mcp_executor`.

#### TC-FORBIDDEN-007 - Agent construction performance: p99 delta ≤ 5 ms

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-2, AC-NFR-2-1
**Test Type(s)**: Performance
**Automation Level**: Semi-automated
**Target Layer / Location**: Local benchmark run (documented procedure)
**Tags**: @backend, @perf

**Preconditions**:

- A baseline measurement is available from pre-fix code (or last known good measurement) using the same environment.
- A representative agent definition and tool set are available for construction.

**Steps**:

1. Run a repeated agent construction loop (sufficient iterations for stable percentiles) for:
   - agent with `forbidden_effects=["write"]`, and
   - agent with empty `forbidden_effects`.
2. Compute p99 construction latency for both pre-fix baseline and post-fix.
3. Compare the p99 delta attributable to the change.

**Expected Outcome**:

- p99 delta (post-fix vs baseline) for the enforcement path is ≤ 5 ms.
- If baseline is unavailable, record the measurement as a TODO and track follow-up (see Section 8).

## 6. Environments and Test Data

- **Test runner**: pytest with `--asyncio-mode=auto`.
- **DB**: in-memory SQLite (`sqlite+aiosqlite:///:memory:`) via existing fixtures.
- **Test data**:
  - Agent definition(s):
    - with `forbidden_effects=["write"]`,
    - with `forbidden_effects` empty/null.
  - Tool sets including at least one tool that classifies as `"write"` and one that does not.

## 7. Automation Plan and Implementation Mapping

| TC-ID | Planned test implementation | Primary assertions |
|---|---|---|
| TC-FORBIDDEN-001 | `pytest` unit test in `tests/test_agent_factory.py` | write-classified tools excluded without `test_run_id` |
| TC-FORBIDDEN-002 | `pytest` integration test with SQLite in-memory and event spy | tools excluded + MCPInvocation persisted + `mcp.denied` emitted |
| TC-FORBIDDEN-003 | `pytest` unit test in `tests/test_agent_factory.py` | no changes when `forbidden_effects` empty/null |
| TC-FORBIDDEN-004 | `pytest` unit test using log capture | exactly one WARNING per excluded tool; includes required structured fields |
| TC-FORBIDDEN-005 | `pytest` integration test with SQLite in-memory | zero MCPInvocation records when `test_run_id` absent |
| TC-FORBIDDEN-006 | Manual repo check (or future CI lint check) | file absent and no references |
| TC-FORBIDDEN-007 | Local benchmark procedure | p99 delta ≤ 5 ms (or TODO if baseline missing) |

## 8. Risks, Assumptions, and Open Questions

**Risks affecting testability**:

- Capturing `mcp.denied` emission may depend on internal event plumbing not exposed to tests; may require a spy/mocking seam aligned with existing Test Lab tests.

**Assumptions (from spec)**:

- `guarded_mcp_executor.py` has zero callers at time of deletion.
- `create_agentscope_agent` is the relevant agent construction path.
- External services are not contacted during tests; mocks/spies are sufficient.

**Open Questions (from spec + test planning)**:

- OQ-1 (spec): Are there additional callers of `create_agentscope_agent` that pass `test_run_id`, and do they require full audit or log-only?
- OQ-2 (spec): Should non-Test-Lab WARNING logs be rate-limited/deduplicated to prevent log flooding?
- OQ-3 (test planning): What is the canonical way in this repo to capture/assert `mcp.denied` emission in tests (fixture, event bus spy, or direct function mock)?
- OQ-4 (test planning): What is the agreed baseline source for the ≤ 5 ms p99 delta requirement (local measurement, CI job, or pre-fix benchmark artifact)?

## 9. Plan Revision Log

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-04-25 | mbensass | Initial test plan for BUG-3 (Proposed) |

## 10. Test Execution Log

| Date (UTC) | Executor | Environment | TC-IDs Executed | Result | Notes |
|---|---|---|---|---|---|
| (not run) |  |  |  |  |  |
