---
id: chg-GH-17-test-plan
status: Proposed
created: 2026-04-27T00:00:00Z
last_updated: 2026-04-27T00:00:00Z
owners:
  - mbensass
service: hotel_orchestrateur / pipeline_executor
labels:
  - async
  - sse
  - pipeline
  - dag
  - performance
links:
  change_spec: doc/changes/2026-04/2026-04-27--GH-17--pipeline-job-async-sse-dag/chg-GH-17-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: minor
summary: |
  Validate the new async pipeline run model (202 Accepted), SSE progress streaming, per-stage timeout isolation,
  and DAG parallelism (mobility || weather), while preserving backward compatibility for POST /{id}/chat.
---

# Test Plan - Async Pipeline Job Execution with SSE Progress Streaming and DAG Parallelism

## 1. Scope and Objectives

This test plan covers:

- Async run submission, polling, and SSE event streaming for pipeline runs (API-1/2/3).
- Correct stage lifecycle events and terminal run completion event (EVT-1..4).
- DAG parallelism for Stage 2 (`mobility` and `weather`) and correct exception/timeout handling.
- Per-stage timeout isolation (a timed-out stage does not cancel siblings nor prevent downstream stages where possible).
- Agent isolation per stage (no shared mutable state across concurrent coroutines).
- Removal of `probe_fn` from the hot request path.
- Backward compatibility for `POST /{id}/chat`.

Out of scope:

- Frontend SSE integration.
- Redis-backed run store (v2).
- AuthN/AuthZ changes (not part of this change).

## 2. References

- Change specification: `doc/changes/2026-04/2026-04-27--GH-17--pipeline-job-async-sse-dag/chg-GH-17-spec.md`
- Testing strategy: `.ai/rules/testing-strategy.md`
- Implementation plan: _Not present at time of writing (link in front matter is null)_

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| Spec ID | Coverage Status | Covered By |
|---|---|---|
| F-1 | Covered | TC-PIPELINE-101, TC-PIPELINE-201 |
| F-2 | Covered | TC-PIPELINE-102, TC-PIPELINE-202 |
| F-3 | Covered | TC-PIPELINE-103, TC-PIPELINE-203 |
| F-4 | Covered | TC-PIPELINE-104, TC-PIPELINE-301 |
| F-5 | Covered | TC-PIPELINE-105, TC-PIPELINE-302 |
| F-6 | Covered | TC-PIPELINE-106, TC-PIPELINE-204 |
| F-7 | Covered | TC-PIPELINE-107, TC-PIPELINE-303 |

| AC ID | Coverage Status | Covered By |
|---|---|---|
| AC-F1-1 | Covered | TC-PIPELINE-201 |
| AC-F2-1 | Covered | TC-PIPELINE-202 |
| AC-F3-1 | Covered | TC-PIPELINE-203 |
| AC-F4-1 | Covered | TC-PIPELINE-301 |
| AC-F5-1 | Covered | TC-PIPELINE-302 |
| AC-F6-1 | Covered | TC-PIPELINE-204 |
| AC-F7-1 | Covered | TC-PIPELINE-303 |
| AC-NFR7-1 | Covered | TC-PIPELINE-401 |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| Interface ID | Coverage Status | Covered By |
|---|---|---|
| API-1 (POST /runs) | Covered | TC-PIPELINE-201 |
| API-2 (GET /runs/{run_id}) | Covered | TC-PIPELINE-202 |
| API-3 (GET /runs/{run_id}/events) | Covered | TC-PIPELINE-203 |
| EVT-1 stage_started | Covered | TC-PIPELINE-103, TC-PIPELINE-203 |
| EVT-2 stage_completed | Covered | TC-PIPELINE-103, TC-PIPELINE-203 |
| EVT-3 stage_failed | Covered | TC-PIPELINE-105, TC-PIPELINE-203, TC-PIPELINE-304 |
| EVT-4 run_complete | Covered | TC-PIPELINE-103, TC-PIPELINE-203 |
| DM-1 RunRecord | Covered | TC-PIPELINE-102, TC-PIPELINE-202, TC-PIPELINE-501 |
| DM-2 StageRecord | Covered | TC-PIPELINE-102, TC-PIPELINE-202 |

### 3.3 Non-Functional Coverage (NFR-#)

| NFR ID | Coverage Status | Covered By | Notes |
|---|---|---|---|
| NFR-1 Latency (POST /runs P99 ≤ 500ms) | Partial | TC-PIPELINE-205 | CI-stable latency/P99 may require perf harness; see Section 8 |
| NFR-2 Concurrency (≥10 concurrent runs) | Covered | TC-PIPELINE-206 | Uses mocked stages to avoid external calls |
| NFR-3 Timeout isolation | Covered | TC-PIPELINE-302 | Also verified at unit-level in TC-PIPELINE-105 |
| NFR-4 SSE reliability (drop does not corrupt; poll recovers state) | Covered | TC-PIPELINE-207 | Poll-based recovery per spec |
| NFR-5 Memory (evict completed runs after ≥1h TTL) | TODO | TC-PIPELINE-502 | Depends on run store API/time injection; see Section 8 |
| NFR-6 Thread safety (no shared mutable state) | Covered | TC-PIPELINE-303 | Verifies distinct agent instances |
| NFR-7 Backward compat | Covered | TC-PIPELINE-401 | Regression coverage for POST /{id}/chat |

## 4. Test Types and Layers

Aligned with `.ai/rules/testing-strategy.md`:

- **Unit** (`tests/unit/`): pure logic without I/O; heavy use of mocks.
- **Integration** (`tests/integration/` and `tests/services/`): FastAPI endpoints via `httpx.TestClient` (or AsyncClient if used in repo), validate end-to-end request/response behavior with a real app instance.
- **Backend API E2E** (`tests/e2e/`): system-level tests that exercise the running API surface through HTTP-like calls and verify externally observable behavior across the async run lifecycle (submission → events → polling).

## 5. Test Scenarios

### 5.1 Scenario Index

| TC ID | Title | Related IDs | Test Type(s) | Automation |
|---|---|---|---|---|
| TC-PIPELINE-101 | Build run record and state transitions | F-1, AC-F1-1, DM-1 | Unit | Automated |
| TC-PIPELINE-102 | Persist stage records and final result shape | F-2, AC-F2-1, DM-1, DM-2 | Unit | Automated |
| TC-PIPELINE-103 | Emit SSE event sequence per stage + terminal | F-3, AC-F3-1, EVT-1, EVT-2, EVT-3, EVT-4 | Unit | Automated |
| TC-PIPELINE-104 | Execute DAG Stage 2 in parallel (timing envelope) | F-4, AC-F4-1 | Unit | Automated |
| TC-PIPELINE-105 | Enforce per-stage timeout and isolate failures | F-5, AC-F5-1, NFR-3 | Unit | Automated |
| TC-PIPELINE-106 | Hot path does not call probe_fn | F-6, AC-F6-1 | Unit | Automated |
| TC-PIPELINE-107 | Stage agent instances are isolated | F-7, AC-F7-1, NFR-6 | Unit | Automated |
| TC-PIPELINE-201 | POST /runs returns 202 + URLs quickly | API-1, AC-F1-1, NFR-1 | Integration, E2E | Automated |
| TC-PIPELINE-202 | GET /runs/{run_id} returns completed result | API-2, AC-F2-1 | Integration, E2E | Automated |
| TC-PIPELINE-203 | SSE stream: per-stage events + run_complete | API-3, AC-F3-1 | Integration, E2E | Automated |
| TC-PIPELINE-204 | /runs endpoints never call probe_fn | AC-F6-1 | Integration | Automated |
| TC-PIPELINE-205 | POST /runs latency budget check (non-flaky mode) | NFR-1 | Integration | Semi-automated |
| TC-PIPELINE-206 | 10 concurrent runs do not starve event loop | NFR-2 | Integration | Automated |
| TC-PIPELINE-207 | SSE disconnect does not corrupt state; poll recovers | NFR-4 | Integration | Automated |
| TC-PIPELINE-301 | Stage 2 wall-clock is bounded by max(stage) + overhead | AC-F4-1 | E2E | Automated |
| TC-PIPELINE-302 | mobility timeout does not cancel weather or budget_fit | AC-F5-1, NFR-3 | E2E | Automated |
| TC-PIPELINE-303 | Parallel stage execution uses distinct agents per stage | AC-F7-1, NFR-6 | E2E | Automated |
| TC-PIPELINE-304 | stage_failed errors are sanitized (no stack traces/PII) | AC-F3-1, EVT-3 | Integration | Automated |
| TC-PIPELINE-401 | POST /{id}/chat backward compatibility regression | AC-NFR7-1, NFR-7 | Integration | Automated |
| TC-PIPELINE-501 | Status endpoint reflects stage lifecycle and timestamps | NFR-4, DM-1, DM-2 | Integration | Automated |
| TC-PIPELINE-502 | Completed runs are evicted after TTL (≥1h) | NFR-5 | Unit | TODO |

### 5.2 Scenario Details

#### TC-PIPELINE-101 - Build run record and state transitions

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-1, AC-F1-1, DM-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- A run record/state machine component exists (e.g., `RunRecord` with status transitions).

**Steps**:

1. Create a new run record for a given `agent_id`.
2. Transition statuses in allowed order: `PENDING → RUNNING → COMPLETED`.
3. Attempt an invalid transition (e.g., `COMPLETED → RUNNING`).

**Expected Outcome**:

- Run status transitions follow the spec-defined lifecycle.
- Invalid transitions are rejected (exception or no-op with clear error).

#### TC-PIPELINE-102 - Persist stage records and final result shape

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-2, AC-F2-1, DM-1, DM-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- Stage records exist and are attachable to the run record.

**Steps**:

1. Append stage records as each stage starts and completes.
2. Mark run completed and set final `result`.
3. Serialize to response shape expected by `GET /runs/{run_id}`.

**Expected Outcome**:

- Response contains `run_id`, `status`, `result` when completed, and `stages[]` entries with stage status and timestamps.

#### TC-PIPELINE-103 - Emit SSE event sequence per stage + terminal

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-1, EVT-1, EVT-2, EVT-3, EVT-4
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend @api

**Preconditions**:

- An event emitter exists that produces SSE events for stage lifecycle.

**Steps**:

1. Simulate a run with stages: `discover`, `mobility`, `weather`, `budget_fit`.
2. Emit `stage_started` and `stage_completed` for successful stages.
3. Emit `run_complete` terminal event.

**Expected Outcome**:

- At least one `stage_started` and one `stage_completed` or `stage_failed` event is produced per stage.
- A final `run_complete` event is produced.
- All emitted event timestamps (`ts`) are ISO-8601 UTC strings.

#### TC-PIPELINE-104 - Execute DAG Stage 2 in parallel (timing envelope)

**Scenario Type**: Edge Case
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/` or `tests/services/`
**Tags**: @backend

**Preconditions**:

- Stage executor supports parallel execution for Stage 2.

**Steps**:

1. Stub `mobility` stage to await for `t1` and `weather` for `t2`.
2. Execute Stage 2 using the DAG model.
3. Measure elapsed time for Stage 2.

**Expected Outcome**:

- Stage 2 elapsed time is approximately `max(t1, t2)` (within a small overhead), indicating concurrency.

#### TC-PIPELINE-105 - Enforce per-stage timeout and isolate failures

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-1, NFR-3
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- Each stage is wrapped with a per-stage timeout (e.g., `asyncio.wait_for`).

**Steps**:

1. Stub `mobility` to hang beyond its timeout.
2. Stub `weather` to succeed within its timeout.
3. Execute Stage 2 with `return_exceptions=True` handling.
4. Continue to Stage 3 (`budget_fit`) where possible.

**Expected Outcome**:

- `mobility` produces a stage-level failure (timeout) and does not cancel `weather`.
- Execution proceeds to Stage 3 as per spec intent.

#### TC-PIPELINE-106 - Hot path does not call probe_fn

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-6, AC-F6-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- `agent_factory` historically invoked `probe_fn` in hot path.

**Steps**:

1. Monkeypatch `probe_fn` to raise an exception if called.
2. Construct the dependency graph used by `/runs` endpoints (agent creation/tool listing).
3. Execute the hot-path code that should not trigger `probe_fn`.

**Expected Outcome**:

- No call to `probe_fn` occurs.

#### TC-PIPELINE-107 - Stage agent instances are isolated

**Scenario Type**: Corner Case
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-7, AC-F7-1, NFR-6
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- Stage execution constructs an agent instance per stage.

**Steps**:

1. Monkeypatch agent factory to return a new object per call with a unique marker.
2. Run Stage 2 in parallel.
3. Capture the agent instance used by each stage.

**Expected Outcome**:

- `mobility` and `weather` use different agent instances.
- No shared mutable state is observed between stage executions.

#### TC-PIPELINE-201 - POST /runs returns 202 + URLs quickly

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: API-1, AC-F1-1, NFR-1
**Test Type(s)**: Integration, E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/` (primary), `tests/e2e/` (system-level)
**Tags**: @backend @api @e2e

**Preconditions**:

- FastAPI app is instantiable in tests.
- Pipeline execution is stubbed to avoid real LLM/MCP calls.

**Steps**:

1. Call `POST /api/agents/{id}/runs` with a valid payload.
2. Measure request handling time in the test process (best-effort; see NFR-1 notes).

**Expected Outcome**:

- Response status is `202`.
- Body contains `run_id`, `status_url`, `events_url`.
- Handling time is within the latency budget when pipeline execution is not awaited in the request path.

#### TC-PIPELINE-202 - GET /runs/{run_id} returns completed result

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: API-2, AC-F2-1
**Test Type(s)**: Integration, E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`, `tests/e2e/`
**Tags**: @backend @api @e2e

**Preconditions**:

- A run can be created with stubbed stages that complete deterministically.

**Steps**:

1. Create a run via `POST /runs`.
2. Poll `GET /api/agents/{id}/runs/{run_id}` until terminal state or a short timeout.

**Expected Outcome**:

- The final response contains `status: completed` and a `result`.

#### TC-PIPELINE-203 - SSE stream: per-stage events + run_complete

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: API-3, EVT-1, EVT-2, EVT-3, EVT-4, AC-F3-1
**Test Type(s)**: Integration, E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`, `tests/e2e/`
**Tags**: @backend @api @e2e

**Preconditions**:

- SSE endpoint streams events as `text/event-stream`.

**Steps**:

1. Create a run via `POST /runs`.
2. Connect to `GET /api/agents/{id}/runs/{run_id}/events`.
3. Collect SSE events until `run_complete` is received.

**Expected Outcome**:

- For each stage, at least one `stage_started` and one terminal stage event (`stage_completed` or `stage_failed`) is received.
- A final `run_complete` event is received.

#### TC-PIPELINE-204 - /runs endpoints never call probe_fn

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: High
**Related IDs**: AC-F6-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend @api

**Preconditions**:

- Ability to monkeypatch the `probe_fn` symbol used by the router dependencies.

**Steps**:

1. Monkeypatch `probe_fn` to raise if invoked.
2. Call `POST /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/events`.

**Expected Outcome**:

- None of the endpoints invoke `probe_fn`.

#### TC-PIPELINE-205 - POST /runs latency budget check (non-flaky mode)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-1
**Test Type(s)**: Integration
**Automation Level**: Semi-automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend @perf

**Preconditions**:

- Pipeline execution is fully stubbed so that request path does not perform long I/O.

**Steps**:

1. Run a loop of N requests to `POST /runs` (N chosen to reduce noise).
2. Record response times in-process.

**Expected Outcome**:

- Measured times strongly indicate a fast handler; if strict P99 ≤ 500ms is unstable in CI, record as evidence and treat as a local/perf-environment gate.

#### TC-PIPELINE-206 - 10 concurrent runs do not starve event loop

**Scenario Type**: Edge Case
**Impact Level**: Critical
**Priority**: High
**Related IDs**: NFR-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend

**Preconditions**:

- Stages are stubbed to be short and non-blocking.

**Steps**:

1. Start 10 runs concurrently (async client or thread pool around TestClient).
2. For each run, open SSE stream and wait for `run_complete`.

**Expected Outcome**:

- All 10 runs complete within a reasonable bound.
- No deadlocks / hangs are observed.

#### TC-PIPELINE-207 - SSE disconnect does not corrupt state; poll recovers

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-4
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend @api

**Preconditions**:

- Run continues server-side even if SSE client disconnects.

**Steps**:

1. Start a run and connect to SSE events.
2. After receiving the first `stage_started`, disconnect the SSE client.
3. Poll `GET /runs/{run_id}` until completion.

**Expected Outcome**:

- Run progresses to a terminal state despite the SSE disconnect.
- `GET /runs/{run_id}` reflects the last known state and final result when done.

#### TC-PIPELINE-301 - Stage 2 wall-clock is bounded by max(stage) + overhead

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: AC-F4-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/`
**Tags**: @backend @api @e2e

**Preconditions**:

- E2E harness can execute the app and observe stage timing (via events or status endpoint timestamps).

**Steps**:

1. Stub mobility duration = `t1`, weather duration = `t2`.
2. Run a full pipeline.
3. Compute Stage 2 elapsed time from stage timestamps (or by correlating event `ts`).

**Expected Outcome**:

- Stage 2 elapsed time ≤ `max(t1, t2) + 200ms`.

#### TC-PIPELINE-302 - mobility timeout does not cancel weather or budget_fit

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: AC-F5-1, NFR-3
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/`
**Tags**: @backend @api @e2e

**Preconditions**:

- Ability to force `mobility` stage timeout and keep `weather` successful.

**Steps**:

1. Start a run.
2. Observe SSE events during Stage 2.
3. Confirm `mobility` emits `stage_failed` due to timeout.
4. Confirm `weather` emits `stage_completed`.
5. Confirm Stage 3 (`budget_fit`) emits `stage_started` and completes.

**Expected Outcome**:

- Timeout is isolated to `mobility`; other stages proceed.

#### TC-PIPELINE-303 - Parallel stage execution uses distinct agents per stage

**Scenario Type**: Corner Case
**Impact Level**: Critical
**Priority**: High
**Related IDs**: AC-F7-1, NFR-6
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/`
**Tags**: @backend @api @e2e

**Preconditions**:

- Agent factory can be configured to include an instance identifier in stage output (test-only stub).

**Steps**:

1. Run a pipeline where each stage returns output containing an agent instance id.
2. Compare mobility and weather instance ids.

**Expected Outcome**:

- Mobility and weather outputs indicate distinct agent instances.

#### TC-PIPELINE-304 - stage_failed errors are sanitized (no stack traces/PII)

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: AC-F3-1, EVT-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend @api

**Preconditions**:

- A stage can be forced to raise an exception.

**Steps**:

1. Start a run with a stage that raises a synthetic exception containing a recognizable marker.
2. Read the corresponding `stage_failed` SSE event.

**Expected Outcome**:

- The client-facing `error` field is sanitized (no Python traceback, no internal stack frames).
- The raw exception message is not blindly echoed if it contains sensitive data.

**Notes / Clarifications** (optional):

- Also validates the spec’s client-facing error sanitization requirement for `stage_failed` SSE events.

#### TC-PIPELINE-401 - POST /{id}/chat backward compatibility regression

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: AC-NFR7-1, NFR-7
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend @api

**Preconditions**:

- A representative previously-valid chat request payload exists.

**Steps**:

1. Call `POST /api/agents/{id}/chat` with a previously-valid payload.
2. Compare response structure and key semantics against the pre-change baseline expectations.

**Expected Outcome**:

- Response schema and semantics match prior behavior (no breaking changes).

#### TC-PIPELINE-501 - Status endpoint reflects stage lifecycle and timestamps

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-4, DM-1, DM-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend @api

**Preconditions**:

- `GET /runs/{run_id}` exposes stage list and timestamps.

**Steps**:

1. Start a run.
2. Poll status while running.
3. Validate that stages move from not-started → started → completed/failed with increasing timestamps.

**Expected Outcome**:

- Status response reflects progression accurately.
- Timestamp fields present are ISO-8601 UTC.

#### TC-PIPELINE-502 - Completed runs are evicted after TTL (≥1h)

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Low
**Related IDs**: NFR-5
**Test Type(s)**: Unit
**Automation Level**: TODO
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- Run store implements TTL eviction and provides a way to control time in tests (dependency injection or clock abstraction).

**Steps**:

1. Create and complete a run record.
2. Advance time by ≥ 1 hour.
3. Trigger eviction (automatic tick or explicit cleanup call).

**Expected Outcome**:

- Completed run records are removed/evicted after TTL.

**Notes / Clarifications**:

- If the implementation does not support controllable time, this scenario remains TODO and requires a store design adjustment.

## 6. Environments and Test Data

### Environments

- Local + CI pytest environment (per testing strategy).
- Tests must not require external network access.

### Test Data

- Use deterministic stub stage outputs (e.g., fixed JSON-like dicts) to verify status/result fields.
- Use synthetic failures/timeouts for negative-path coverage.

### Required Mocks / Fakes

- **LLM (Ollama cloud)**: replace with a deterministic fake response provider.
- **MCP Tavily**: replace with a deterministic fake client/transport.
- **AgentScope ReActAgent**: replace agent instantiation with a lightweight stub that can return a known output and expose an instance identifier.
- **Stage functions**: for timing tests, use `asyncio.sleep()` stubs under short durations.

## 7. Automation Plan and Implementation Mapping

### Proposed test files to create under `tests/`

> File names follow `.ai/rules/testing-strategy.md`: `test_<component>_<behavior>.py`.

- `tests/unit/test_pipeline_runner_state_machine.py`
  - TC-PIPELINE-101
- `tests/unit/test_run_record_stage_record_serialization.py`
  - TC-PIPELINE-102
- `tests/unit/test_sse_event_emission_schema.py`
  - TC-PIPELINE-103, TC-PIPELINE-304 (schema/sanitization at unit-level if feasible)
- `tests/unit/test_pipeline_executor_dag_parallelism.py`
  - TC-PIPELINE-104, TC-PIPELINE-105
- `tests/unit/test_agent_factory_hot_path_probe_free.py`
  - TC-PIPELINE-106
- `tests/unit/test_stage_agent_isolation.py`
  - TC-PIPELINE-107

- `tests/unit/test_run_store_ttl_eviction.py`
  - TC-PIPELINE-502

- `tests/integration/test_agents_runs_submit_202.py`
  - TC-PIPELINE-201, TC-PIPELINE-205
- `tests/integration/test_agents_runs_status_polling.py`
  - TC-PIPELINE-202, TC-PIPELINE-501
- `tests/integration/test_agents_runs_sse_events.py`
  - TC-PIPELINE-203, TC-PIPELINE-207, TC-PIPELINE-304
- `tests/integration/test_agents_runs_probe_free.py`
  - TC-PIPELINE-204
- `tests/integration/test_agents_chat_backward_compat.py`
  - TC-PIPELINE-401
- `tests/integration/test_runs_concurrency_10.py`
  - TC-PIPELINE-206

- `tests/e2e/test_runs_full_flow_sse_and_polling.py`
  - TC-PIPELINE-201, TC-PIPELINE-202, TC-PIPELINE-203
- `tests/e2e/test_runs_stage2_parallelism_timing.py`
  - TC-PIPELINE-301
- `tests/e2e/test_runs_timeout_isolation.py`
  - TC-PIPELINE-302
- `tests/e2e/test_runs_agent_isolation.py`
  - TC-PIPELINE-303

### Notes on implementing integration/E2E

- Prefer `httpx.TestClient` (per strategy) for integration tests.
- For async SSE tests, use an async-capable client if present in the repo’s existing test harness; otherwise, implement a small SSE parser that reads the streaming body and extracts `event:` and `data:` frames.
- All external calls must be mocked (LLM + MCP Tavily).

## 8. Risks, Assumptions, and Open Questions

### Risks

- **R-TP-1 (Flaky timing assertions)**: strict latency and 200ms overhead bounds can be noisy in CI.
  - Mitigation: rely on deterministic stubs, assert broad envelopes in CI; keep strict P99 validation as a dedicated perf job/environment.

- **R-TP-2 (SSE test harness complexity)**: SSE parsing and streaming in tests may require async client support.
  - Mitigation: provide a minimal, well-tested SSE parsing helper for tests.

### Assumptions

- The `/runs` endpoints are implemented as additive endpoints under `/api/agents/{id}/...` as per spec.
- The code allows dependency injection or monkeypatching for agent creation and external integrations so tests can be fully offline.

### Open Questions

- **OQ-TP-1**: What is the canonical way in this repo to test SSE streaming responses (sync TestClient vs AsyncClient)?
- **OQ-TP-2**: Will the run store expose an eviction hook / controllable clock for TTL tests (NFR-5), or should NFR-5 be validated manually?

## 9. Plan Revision Log

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-04-27 | @test-plan-writer | Initial test plan (Proposed) for GH-17 |

## 10. Test Execution Log

| Date (UTC) | Executor | Environment | TC IDs Executed | Result | Notes |
|---|---|---|---|---|---|
| Not executed yet |  |  |  |  |  |
