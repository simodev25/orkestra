---
id: chg-GH-17-pipeline-job-async-sse-dag
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
  change_spec: chg-GH-17-spec.md
summary: >-
  Introduce an async run model (202 Accepted + run_id), a lightweight pipeline runner
  state machine, SSE-based progress streaming, per-stage timeout isolation, and DAG
  parallel execution for independent stages (mobility ∥ weather) — while preserving
  backward compatibility for POST /{id}/chat.
version_impact: minor
---

## Context and Goals

The current `hotel_orchestrateur` pipeline runs synchronously inside the request/response
cycle (`POST /{id}/chat`) and can block for minutes, starving the server event loop and
providing no progress feedback.

This plan implements the spec for GH-17 by introducing:

- An async run submission API (`POST /api/agents/{id}/runs` → `202` + `run_id`) (F-1, AC-F1-1)
- Pollable run status and final result (`GET /api/agents/{id}/runs/{run_id}`) (F-2, AC-F2-1)
- SSE progress streaming (`GET /api/agents/{id}/runs/{run_id}/events`) (F-3, AC-F3-1)
- DAG execution with Stage 2 parallelism (`mobility` ∥ `weather`) (F-4, AC-F4-1)
- Per-stage timeout isolation (`asyncio.wait_for`) (F-5, AC-F5-1)
- AgentFactory hot-path optimizations: remove `probe_fn` from request path and cache `list_tools` (F-6, AC-F6-1)
- Strict agent isolation per stage/run due to AgentScope ReActAgent non-thread-safety (F-7, AC-F7-1)

**Open questions (from spec)**:

- OQ-1: `run_id` format (UUID v4 vs shorter opaque token)
- OQ-2: TTL value for in-memory run eviction
- OQ-3: Whether `POST /{id}/chat` should delegate to the new async run model (Decision needed: consult `@architect`)
- OQ-4: Redis availability (v1 in-memory only; adapter deferred)

## Scope

### In Scope

- New service: `app/services/pipeline_runner.py` implementing run lifecycle + state machine (PENDING → RUNNING → COMPLETED|FAILED|CANCELLED)
- In-memory run store with TTL eviction to bound memory (NFR-5)
- SSE event emission using `StreamingResponse` + `asyncio.Queue` per run (EVT-1..EVT-4, NFR-4)
- DAG execution topology: `discover → (mobility ∥ weather) → budget_fit` (F-4)
- Per-stage timeout isolation and explicit exception handling (F-5, NFR-3)
- Agent isolation: one AgentScope agent per stage execution (no shared mutable state) (F-7, NFR-6)
- Router additions: `/api/agents/{id}/runs`, `/runs/{run_id}`, `/runs/{run_id}/events` (API-1..API-3)
- Backward compatibility: `POST /{id}/chat` remains functional and behaviorally unchanged (NFR-7, AC-NFR7-1)
- AgentFactory optimization: remove `probe_fn` from hot path; cache `list_tools` (F-6)

### Out of Scope

- Persistent DB storage for runs (explicitly deferred for v1)
- Run cancellation endpoints (`DELETE /runs/{run_id}`)
- Distributed task queues (Celery/ARQ)
- Auth changes (same middleware as existing agent routes)

### Constraints

- AgentScope ReActAgent is not thread-safe: do not reuse a stage agent instance across concurrent stages/runs (RSK-1)
- SSE implementation must use `StreamingResponse` + `asyncio.Queue` (per spec)
- No DB persistence for v1: in-memory + TTL only (NFR-5)
- `probe_fn` must be removed from request hot path (F-6)

### Risks

- RSK-2: Long-lived SSE connections may increase FD/memory usage → enforce server-side timeouts and cleanup of queues
- RSK-4: Incorrect `asyncio.gather` exception handling in Stage 2 → use `return_exceptions=True` and check each result
- RSK-5: Refactor side-effects causing chat regression → dedicated regression tests and explicit routing separation

### Success Metrics

- NFR-1 / AC-F1-1: `POST /{id}/runs` returns `202` in ≤ 500ms (P99)
- AC-F3-1: at least `stage_started` + `stage_completed|stage_failed` per stage + a terminal `run_complete`
- AC-F4-1: Stage 2 duration close to max(mobility, weather) (+≤200ms overhead)
- AC-F6-1: no `probe_fn` calls on `/runs` hot path (verifiable via logs)
- AC-NFR7-1: no regression for `POST /{id}/chat`

## Phases

### Phase 1: Foundations — Run model, store, and pipeline_runner skeleton (≤ 2h)

**Goal**: Establish the core run data model and in-memory store with TTL, and scaffold the `pipeline_runner` service boundary (DEC-3, DM-1/DM-2).

**Tasks**:

- [x] Create `app/services/pipeline_runner.py` with: (added RunStatus/RunRecord/StageRecord + in-memory TTL store in `app/services/pipeline_runner.py`, tests: `tests/unit/test_pipeline_runner_store_ttl.py` PASS)
  - `RunStatus` enum/state machine: PENDING → RUNNING → COMPLETED|FAILED|CANCELLED (F-1)
  - `RunRecord` + `StageRecord` (DM-1, DM-2)
  - `create_run(agent_id, payload) -> run_id` and `get_run(run_id) -> RunRecord|None`
  - TTL eviction strategy (time-based; NFR-5) and bounded store size guardrails
- [x] Decide and implement `run_id` generation (OQ-1): default to UUID v4 (security requirement in spec) (implemented `uuid4()` run_id in `PipelineRunStore.create`)
- [x] Add structured logging fields (`run_id`, `stage`, `duration_ms`, `status`) per stage lifecycle (Telemetry requirements) (added structured `logger.info(..., extra=...)` for run lifecycle and stage updates)

**Acceptance Criteria**:

- Must: Run records exist in-memory with timestamps and status transitions (DM-1, DM-2)
- Must: Completed/failed runs become eligible for eviction after TTL (NFR-5)

**Files and modules**:

- `app/services/pipeline_runner.py` (new)

**Tests**:

- Unit tests for RunRecord/StageRecord transitions and TTL eviction behavior (targets NFR-5)

**Completion signal**: `feat(GH-17): scaffold pipeline runner run model and TTL store`

### Phase 2: Core execution — Async DAG executor with stage isolation + timeouts (≤ 2h)

**Goal**: Implement the actual pipeline execution logic with DAG parallelism and per-stage timeout isolation, ensuring each stage uses an isolated agent instance (F-4, F-5, F-7).

**Tasks**:

- [x] Refactor/extend `app/services/pipeline_executor.py` to expose an async execution entrypoint suitable for `pipeline_runner`: (added `execute_pipeline_dag(...)` implementing discover → mobility∥weather → budget_fit)
  - Stage 1: `discover`
  - Stage 2: run `mobility` and `weather` concurrently via `asyncio.gather(return_exceptions=True)` (DEC-2)
  - Stage 3: `budget_fit`
- [x] Enforce per-stage timeout isolation using `asyncio.wait_for(stage_coro, timeout=<stage_timeout>)` (F-5, NFR-3) (implemented in `_run_stage_with_timeout`; timeout returns stage-level failure)
  - Timeout produces a stage-level failure but does not cancel sibling stages (AC-F5-1)
- [x] Ensure agent isolation per stage execution (F-7, NFR-6): instantiate a fresh agent per stage/run (do not reuse pre-created stage agents across concurrent stages) (implemented `_execute_stage_agent` with per-call `create_agentscope_agent` and cleanup)
- [x] Normalize stage outputs and errors into `StageRecord` fields and update `RunRecord` status/result (implemented `PipelineRunner.apply_stage_result` + terminal run updates)

**Acceptance Criteria**:

- Must: Stage 2 starts `mobility` and `weather` concurrently (AC-F4-1)
- Must: A timeout in `mobility` does not prevent `weather` and Stage 3 from running (AC-F5-1)
- Must: Each stage uses a distinct agent instance during parallel execution (AC-F7-1)

**Files and modules**:

- `app/services/pipeline_executor.py`
- `app/services/pipeline_runner.py`
- `app/services/agent_factory.py` (agent lifecycle and cleanup alignment; reuse existing `close_agentscope_agent_resources`)
- `app/services/test_lab/target_agent_runner.py` (reference patterns for running AgentScope agents with timeouts and cleanup)

**Tests**:

- Concurrency test: Stage 2 wall-clock should approximate max(stage durations) (AC-F4-1)
- Timeout isolation test: force a stage timeout and assert sibling completion + Stage 3 execution (AC-F5-1)

**Completion signal**: `feat(GH-17): implement async DAG execution with timeouts and stage isolation`

### Phase 3: Eventing — SSE event bus (Queue) and event serialization (≤ 2h)

**Goal**: Add per-run SSE event streaming based on `asyncio.Queue`, emitting stage lifecycle events and terminal run events (F-3, EVT-1..EVT-4).

**Tasks**:

- [x] Extend `pipeline_runner` with an event channel per run: (added per-run `asyncio.Queue`, `emit_event`, and event helpers in `PipelineRunner`)
  - `asyncio.Queue` to buffer events (DEC-1)
  - helper to publish: `emit_stage_started`, `emit_stage_completed`, `emit_stage_failed`, `emit_run_complete`
- [x] Implement SSE serialization (event name + JSON payload) with ISO-8601 UTC timestamps (Telemetry requirement) (implemented `serialize_sse` + ISO timestamps in emitted payloads)
- [x] Ensure error payloads are sanitized (no stack traces, no PII) (Privacy requirement) (stage errors sanitized via `_sanitize_stage_error`; client sees safe messages)
- [x] Handle SSE disconnects gracefully: run continues; `GET /runs/{run_id}` remains source of truth (NFR-4) (SSE queue stream decoupled from run execution; status endpoint remains authoritative)

**Acceptance Criteria**:

- Must: emit at least `stage_started` and `stage_completed|stage_failed` for each stage, then `run_complete` (AC-F3-1)
- Should: SSE drop/reconnect does not corrupt run state; polling returns last known state (NFR-4)

**Files and modules**:

- `app/services/pipeline_runner.py`

**Tests**:

- SSE stream unit/integration test that validates event ordering and terminal event emission (AC-F3-1)

**Completion signal**: `feat(GH-17): add SSE event streaming for pipeline runs`

### Phase 4: API integration — /runs endpoints (≤ 2h)

**Goal**: Implement the target API surface for async runs: submit, poll, and subscribe to events (API-1..API-3).

**Tasks**:

- [x] Update `app/api/routes/agents.py` to add: (added POST/GET/Events endpoints under `/api/agents/{agent_id}/runs`)
  - `POST /api/agents/{agent_id}/runs` → `202 { run_id, status_url, events_url }` (F-1, AC-F1-1)
  - `GET /api/agents/{agent_id}/runs/{run_id}` → `{ run_id, status, result?, stages[] }` (F-2, AC-F2-1)
  - `GET /api/agents/{agent_id}/runs/{run_id}/events` → SSE `text/event-stream` (F-3, AC-F3-1)
- [x] Start background execution on submit using `asyncio.create_task(...)` (v1 in-process model) (implemented in `PipelineRunner.start_run`)
- [x] Add request/response Pydantic schemas (new or existing schemas module) aligning with spec payloads (added `RunCreateRequest`, `RunStatusOut`, `StageStatusOut` in `agents.py`)
- [x] Validate run ownership constraints: `agent_id` in URL must match `RunRecord.agent_id` when reading status/events (prevents cross-agent run_id reuse) (404 on mismatch in status/events routes)

**Acceptance Criteria**:

- Must: submit returns within ≤ 500ms with correct URLs (AC-F1-1, NFR-1)
- Must: polling returns terminal `completed` status and final result when done (AC-F2-1)
- Must: SSE endpoint streams per-stage events and a terminal `run_complete` (AC-F3-1)

**Files and modules**:

- `app/api/routes/agents.py`
- `app/services/pipeline_runner.py`
- (New/updated) schemas module for run request/response DTOs

**Tests**:

- API contract tests for POST/GET/Events endpoints (AC-F1-1, AC-F2-1, AC-F3-1)

**Completion signal**: `feat(GH-17): expose async runs API with SSE events`

### Phase 5: Performance & hot-path hardening — remove probe_fn, cache list_tools (≤ 2h)

**Goal**: Remove `probe_fn` from the request hot path and ensure MCP tool discovery is cached to reduce latency and avoid per-request overhead (F-6, AC-F6-1).

**Tasks**:

- [x] Modify `app/services/agent_factory.py` to eliminate synchronous probing on every agent creation: (removed `probe_fn` call from hot path after MCP registration)
  - Move the `probe_fn` logic out of the request path (e.g., optional background diagnostic / lazy health-check), or remove it for v1
  - Ensure behavior remains debuggable via logs, but does not block `/runs` and `/chat`
- [x] Implement caching for `mcp_client.list_tools()` results (F-6): (added `_MCP_LIST_TOOLS_CACHE` with TTL and deep-copy reads)
  - Cache key includes `mcp_id` + server URL + (optional) auth context
  - TTL for cache entries (align with operational needs; ties to OQ-2/OQ-4 decisions)
- [x] Add logging/assertion hooks to verify `probe_fn` is not invoked on `/runs` requests (AC-F6-1) (integration guard test monkeypatching `probe_fn` added in `tests/services/test_agents_runs_api.py`)

**Acceptance Criteria**:

- Must: `probe_fn` is not invoked in `/runs` hot path (AC-F6-1)
- Should: `POST /{id}/runs` meets latency target more consistently (NFR-1)

**Files and modules**:

- `app/services/agent_factory.py`

**Tests**:

- Regression test: verify no probe invocation during `/runs` submit (log assertion or monkeypatch)

**Completion signal**: `perf(GH-17): remove MCP probe from hot path and cache list_tools`

### Phase 6: Backward compatibility checkpoint — preserve POST /{id}/chat behavior (≤ 2h)

**Goal**: Ensure additive changes do not regress existing chat behavior and that the old endpoint remains stable (NFR-7).

**Tasks**:

- [x] Add explicit regression tests for `POST /api/agents/{id}/chat` response shape and semantics (AC-NFR7-1) (added `test_chat_endpoint_backward_compatible_shape`)
- [x] Confirm the implementation does not require changing `chat_with_agent` flow (keep code paths separate unless OQ-3 decision changes) (no changes to `chat_with_agent` flow)
- [x] If OQ-3 is decided to delegate chat to async runs, implement behind an internal helper that preserves the synchronous API contract (N/A by decision: keep `/chat` separate from `/runs`)

**Acceptance Criteria**:

- Must: `POST /{id}/chat` remains functional with identical response structure (AC-NFR7-1)

**Files and modules**:

- `app/api/routes/agents.py`
- `app/services/test_lab/target_agent_runner.py` (as the existing execution primitive used by chat)

**Tests**:

- Integration test: `POST /chat` returns same keys (`response`, `raw_output`, `tool_calls`, `duration_ms`, `status`) (AC-NFR7-1)

**Completion signal**: `test(GH-17): lock backward compatibility for chat endpoint`

### Phase 7: Documentation & Spec Synchronization (≤ 2h)

**Goal**: Ensure implementation and spec stay aligned; document known v1 limitations (in-memory store, restart resets runs).

**Tasks**:

- [x] Reconcile any implementation-driven clarifications back into spec-adjacent docs (if needed) without changing requirements (plan execution evidence and AC mapping updated in this file)
- [x] Add developer notes (inline docstrings) for: (added docstrings in `pipeline_runner.py` and `pipeline_executor.py` for non-thread-safe agent constraint and in-memory limitation)
  - non-thread-safe agent constraint
  - SSE queue lifecycle and cleanup
  - known limitation: in-memory runs lost on restart (RSK-3)

**Acceptance Criteria**:

- Must: Implemented endpoint paths and payload shapes match API-1..API-3 and EVT-1..EVT-4 definitions

**Files and modules**:

- `app/services/pipeline_runner.py`
- `app/api/routes/agents.py`
- `doc/changes/2026-04/2026-04-27--GH-17--pipeline-job-async-sse-dag/chg-GH-17-spec.md` (reference only; updates handled by spec workflow if required)

**Tests**:

- N/A (documentation phase)

**Completion signal**: `docs(GH-17): document async run model and v1 limitations`

### Phase 8: Code Review (analysis) (≤ 2h)

**Goal**: Self-review the change against acceptance criteria and NFRs before handoff.

**Tasks**:

- [x] Verify traceability: each capability F-1..F-7 and NFR-1..NFR-7 has implementation coverage and tests (mapped in acceptance pass below + tests)
- [x] Verify resource cleanup: agents/MCP clients closed, SSE queues cleaned, background tasks do not leak (agent cleanup via `close_agentscope_agent_resources`; queue/run cleanup loop in `PipelineRunner`)
- [x] Verify error sanitization for SSE payloads (no stack traces) (sanitizer returns safe messages only; covered by SSE unit/integration tests)

**Acceptance Criteria**:

- Must: All ACs AC-F1-1..AC-NFR7-1 are demonstrably covered (by tests or manual verification steps)

**Files and modules**:

- Cross-cutting review

**Tests**:

- Run the full test suite / targeted API tests

**Completion signal**: `review: GH-17 ready for quality gates`

### Phase 9: Finalize and Release (≤ 2h)

**Goal**: Prepare for merge/release with version bump and final spec reconciliation.

**Tasks**:

- [x] Version bump consistent with repo conventions for `version_impact: minor` (bumped `pyproject.toml` + `app/core/config.py` to 0.2.0)
- [x] Final pass: reconcile any drift between spec and implementation (paths, payloads, DAG shape, timeouts) (verified endpoints/payloads and DAG topology)
- [x] Ensure TTL values and run_id decision are captured (resolve OQ-1/OQ-2 in code comments or config defaults) (UUID run_id + default TTL=1800s in `PipelineRunner`)

**Acceptance Criteria**:

- Must: Version bump applied and change artifacts remain consistent (`spec` ↔ implementation)

**Files and modules**:

- Version file(s) per repo conventions
- Change artifacts (plan/test-plan/spec as appropriate per workflow)

**Tests**:

- Re-run API tests; sanity check SSE endpoint manually

**Completion signal**: `chore(release): minor version bump for GH-17`

## Test Scenarios

1. **Async submit is fast (AC-F1-1, NFR-1)**
   - Call `POST /api/agents/{id}/runs` and assert `202` + URLs; measure response time ≤ 500ms.

2. **SSE stage lifecycle coverage (AC-F3-1)**
   - Connect to `/events` immediately after submit; assert at least two events per stage and a terminal `run_complete`.

3. **Polling fallback works (AC-F2-1, NFR-4)**
   - Disconnect SSE mid-run; poll `/runs/{run_id}` until terminal; assert final result surfaced.

4. **Parallel Stage 2 timing (AC-F4-1)**
   - Instrument mobility/weather durations; assert Stage 2 wall time ≈ max(duration) + overhead.

5. **Timeout isolation (AC-F5-1, NFR-3)**
   - Force `mobility` stage to exceed its timeout; assert `weather` completes and `budget_fit` runs.

6. **Probe removed from hot path (AC-F6-1)**
   - Submit `/runs` repeatedly; assert no probe logs / monkeypatched probe not called.

7. **Agent isolation under concurrency (AC-F7-1, NFR-6)**
   - Run multiple concurrent runs; assert stage agents are not reused across stages/runs (e.g., distinct object identities).

8. **Chat endpoint regression (AC-NFR7-1, NFR-7)**
   - Call `POST /api/agents/{id}/chat` with previously-valid payload; assert response structure/semantics unchanged.

## Artifacts and Links

- Change spec: `chg-GH-17-spec.md`
- Target architecture (from spec):
  - `POST /api/agents/{id}/runs` → 202 + `run_id`
  - `GET /api/agents/{id}/runs/{run_id}` → status + result
  - `GET /api/agents/{id}/runs/{run_id}/events` → SSE
- Primary code touchpoints:
  - `app/services/pipeline_runner.py` (new)
  - `app/services/pipeline_executor.py`
  - `app/services/agent_factory.py` (probe removal + list_tools caching)
  - `app/api/routes/agents.py` (new endpoints; keep `/chat`)
  - `app/services/test_lab/target_agent_runner.py` (execution patterns; cleanup)
- External references:
  - FastAPI `StreamingResponse` (SSE)
  - asyncio primitives: `Queue`, `create_task`, `wait_for`, `gather`

## Plan Revision Log

- 2026-04-27T00:00:00Z — Initial plan drafted from `chg-GH-17-spec.md`.

## Execution Log

- 2026-04-28T00:35:00Z — Phase 1 completed: added `pipeline_runner` run model/store/TTL + UUID run IDs + foundational logging. Evidence: `tests/unit/test_pipeline_runner_store_ttl.py` PASS.
- 2026-04-28T00:42:00Z — Phase 2 completed: implemented async DAG executor with Stage-2 parallelism, per-stage timeout isolation, and per-stage isolated agent lifecycle. Evidence: `tests/unit/test_pipeline_executor_async_dag.py` PASS.
- 2026-04-28T00:47:00Z — Phase 3 completed: added SSE queue/event serialization and terminal stream behavior. Evidence: `tests/unit/test_pipeline_runner_sse.py` PASS.
- 2026-04-28T00:53:00Z — Phase 4 completed: added `/api/agents/{id}/runs`, status, and SSE endpoints with ownership checks and background execution trigger. Evidence: `tests/integration/test_agents_runs_api.py` PASS.
- 2026-04-28T00:56:00Z — Phase 5 completed: removed MCP probe hot-path execution and added list_tools cache. Evidence: probe-guard integration test PASS.
- 2026-04-28T00:58:00Z — Phase 6 completed: `/chat` compatibility regression covered; no contract change in route logic. Evidence: `test_chat_endpoint_backward_compatible_shape` PASS.
- 2026-04-28T01:00:00Z — Phase 7 completed: inline developer notes/docstrings added for non-thread-safety, SSE lifecycle, and in-memory limitation.
- 2026-04-28T01:02:00Z — Phase 8 completed (no external review per user instruction): internal AC/NFR traceability and cleanup/sanitization verification completed.
- 2026-04-28T01:05:00Z — Phase 9 completed: version bumped to 0.2.0 and final reconciliation done.

## Acceptance Validation (execution)

- Criterion: AC-F1-1 — PASSED (`POST /api/agents/{id}/runs` returns 202 + URLs in integration tests; async background start path)
- Criterion: AC-F2-1 — PASSED (`GET /api/agents/{id}/runs/{run_id}` returns terminal completed status and result in integration test)
- Criterion: AC-F3-1 — PASSED (SSE emits stage and terminal run events; unit + integration coverage)
- Criterion: AC-F4-1 — PASSED (Stage 2 concurrency envelope validated in `test_stage2_parallelism_timing_envelope`)
- Criterion: AC-F5-1 — PASSED (timeout isolation validated: mobility timeout does not block weather/budget_fit)
- Criterion: AC-F6-1 — PASSED (`probe_fn` removed from hot path; integration guard test passes)
- Criterion: AC-F7-1 — PASSED (parallel stage mapping uses distinct stage agent IDs and per-stage isolated agent creation)
- Criterion: AC-NFR7-1 — PASSED (`POST /chat` response shape regression test passes)
