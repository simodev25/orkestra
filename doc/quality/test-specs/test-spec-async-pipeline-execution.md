---
id: TEST-async-pipeline-execution
status: Current
version: 0.2.0
last_updated: 2026-04-28
links:
  related_changes:
    - GH-17
  related_features:
    - SPEC-async-pipeline-execution
  source_test_plan: doc/changes/2026-04/2026-04-27--GH-17--pipeline-job-async-sse-dag/chg-GH-17-test-plan.md
---

# Test Specification: Async Pipeline Execution with SSE Streaming

## Test Strategy

This feature is validated through a three-layer testing approach:

1. **Unit Tests** (`tests/unit/`): Pure logic without I/O; heavy use of mocks
2. **Integration Tests** (`tests/integration/`, `tests/services/`): FastAPI endpoints via `httpx.TestClient` with real app instance
3. **Backend API E2E Tests** (`tests/e2e/`): System-level HTTP tests exercising full async run lifecycle

## Critical Test Scenarios

### Async Run Submission (TC-PIPELINE-201)
**Type**: Happy Path | **Priority**: High | **Layer**: Integration, E2E

**Given** a valid agent ID and message payload  
**When** `POST /api/agents/{id}/runs` is called  
**Then** the API returns `202 Accepted` with `run_id`, `status_url`, and `events_url` in ≤ 500ms

**Validates**: API-1, AC-F1-1, NFR-1

---

### Run Status Polling (TC-PIPELINE-202)
**Type**: Happy Path | **Priority**: High | **Layer**: Integration, E2E

**Given** a completed run  
**When** `GET /api/agents/{id}/runs/{run_id}` is called  
**Then** the response contains `status: completed` and the final `result`

**Validates**: API-2, AC-F2-1

---

### SSE Progress Events (TC-PIPELINE-203)
**Type**: Happy Path | **Priority**: Critical | **Layer**: Integration, E2E

**Given** an active run  
**When** a client connects to `GET /api/agents/{id}/runs/{run_id}/events`  
**Then** the client receives at least one `stage_started` and one terminal stage event (`stage_completed` or `stage_failed`) per stage, followed by a `run_complete` event

**Validates**: API-3, EVT-1..EVT-4, AC-F3-1

---

### DAG Stage 2 Parallelism (TC-PIPELINE-301)
**Type**: Edge Case | **Priority**: Critical | **Layer**: E2E

**Given** a pipeline run  
**When** Stage 2 executes  
**Then** `mobility` and `weather` stages are initiated concurrently and the combined Stage 2 wall-clock duration is ≤ `max(mobility_duration, weather_duration) + 200ms` overhead

**Validates**: AC-F4-1

---

### Per-Stage Timeout Isolation (TC-PIPELINE-302)
**Type**: Negative | **Priority**: Critical | **Layer**: E2E

**Given** the `mobility` stage times out  
**When** Stage 2 executes  
**Then** `weather` still completes normally and `budget_fit` (Stage 3) still executes

**Validates**: AC-F5-1, NFR-3

---

### Agent Isolation Under Concurrency (TC-PIPELINE-303)
**Type**: Corner Case | **Priority**: Critical | **Layer**: E2E

**Given** parallel stage execution in Stage 2  
**When** both stages run concurrently  
**Then** each stage operates on a distinct agent instance with no shared mutable state

**Validates**: AC-F7-1, NFR-6

---

### SSE Disconnect Resilience (TC-PIPELINE-207)
**Type**: Negative | **Priority**: Medium | **Layer**: Integration

**Given** an active SSE connection  
**When** the client disconnects mid-run  
**Then** the run continues to completion and `GET /runs/{run_id}` returns the final state

**Validates**: NFR-4

---

### Hot-Path Probe Removal (TC-PIPELINE-204)
**Type**: Regression | **Priority**: High | **Layer**: Integration

**Given** a hot-path request to any `/runs` endpoint  
**When** the request is processed  
**Then** `probe_fn` is not invoked (verified via monkeypatch guard)

**Validates**: AC-F6-1

---

### Concurrent Run Handling (TC-PIPELINE-206)
**Type**: Edge Case | **Priority**: High | **Layer**: Integration

**Given** 10 concurrent pipeline runs  
**When** all runs execute simultaneously  
**Then** all runs complete without event loop starvation or deadlocks

**Validates**: NFR-2

---

### Chat Endpoint Backward Compatibility (TC-PIPELINE-401)
**Type**: Regression | **Priority**: Critical | **Layer**: Integration

**Given** the existing `POST /{id}/chat` endpoint  
**When** called with any previously-valid payload  
**Then** it returns the same response structure and semantics as before this change

**Validates**: AC-NFR7-1, NFR-7

---

### Error Sanitization (TC-PIPELINE-304)
**Type**: Negative | **Priority**: Medium | **Layer**: Integration

**Given** a stage that raises an exception  
**When** the `stage_failed` SSE event is emitted  
**Then** the error payload is sanitized (no stack traces, no PII)

**Validates**: EVT-3, Privacy requirements

---

## Test Data Requirements

- **Deterministic stub stage outputs**: Fixed JSON-like structures for reproducible validation
- **Synthetic failures/timeouts**: Controlled stage failures for negative-path coverage
- **No external network dependencies**: All LLM and MCP calls are mocked

## Mocking Strategy

- **LLM (Ollama)**: Replace with deterministic fake response provider
- **MCP Tavily**: Replace with deterministic fake client/transport
- **AgentScope ReActAgent**: Stub with lightweight fake that returns known output and exposes instance identifier
- **Stage timing**: Use `asyncio.sleep()` stubs with short durations

## Test File Organization

```
tests/
├── unit/
│   ├── test_pipeline_runner_state_machine.py       # TC-PIPELINE-101
│   ├── test_run_record_stage_record_serialization.py  # TC-PIPELINE-102
│   ├── test_sse_event_emission_schema.py           # TC-PIPELINE-103
│   ├── test_pipeline_executor_dag_parallelism.py   # TC-PIPELINE-104, TC-PIPELINE-105
│   ├── test_agent_factory_hot_path_probe_free.py   # TC-PIPELINE-106
│   ├── test_stage_agent_isolation.py               # TC-PIPELINE-107
│   └── test_run_store_ttl_eviction.py              # TC-PIPELINE-502
├── integration/
│   ├── test_agents_runs_submit_202.py              # TC-PIPELINE-201, TC-PIPELINE-205
│   ├── test_agents_runs_status_polling.py          # TC-PIPELINE-202, TC-PIPELINE-501
│   ├── test_agents_runs_sse_events.py              # TC-PIPELINE-203, TC-PIPELINE-207, TC-PIPELINE-304
│   ├── test_agents_runs_probe_free.py              # TC-PIPELINE-204
│   ├── test_agents_chat_backward_compat.py         # TC-PIPELINE-401
│   └── test_runs_concurrency_10.py                 # TC-PIPELINE-206
└── e2e/
    ├── test_runs_full_flow_sse_and_polling.py      # TC-PIPELINE-201, TC-PIPELINE-202, TC-PIPELINE-203
    ├── test_runs_stage2_parallelism_timing.py      # TC-PIPELINE-301
    ├── test_runs_timeout_isolation.py              # TC-PIPELINE-302
    └── test_runs_agent_isolation.py                # TC-PIPELINE-303
```

## Known Limitations

- **Flaky timing assertions**: Strict latency and overhead bounds can be noisy in CI. Use broad envelopes; delegate P99 validation to dedicated perf environment.
- **TTL eviction testing**: Requires controllable clock or time injection (NFR-5 coverage may be manual if not implemented).

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial test spec derived from GH-17 test plan |
