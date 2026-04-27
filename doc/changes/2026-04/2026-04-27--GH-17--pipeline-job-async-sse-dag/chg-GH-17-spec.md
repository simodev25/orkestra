---
change:
  ref: GH-17
  type: feat
  status: Proposed
  slug: pipeline-job-async-sse-dag
  title: "Async Pipeline Job Execution with SSE Progress Streaming and DAG Parallelism"
  owners: [mbensass]
  service: hotel_orchestrateur / pipeline_executor
  labels: [async, sse, pipeline, dag, performance]
  version_impact: minor
  audience: internal
  security_impact: low
  risk_level: medium
  dependencies:
    internal: [pipeline_executor, agent_factory, agents_router]
    external: [FastAPI StreamingResponse, AgentScope ReActAgent]
---

# CHANGE SPECIFICATION

> **PURPOSE**: Decouple the `hotel_orchestrateur` pipeline execution from the blocking HTTP request cycle by introducing an async job model, real-time SSE progress events, effective per-stage timeouts, and parallel DAG execution for independent stages — while preserving backward compatibility on `POST /{id}/chat`.

---

## 1. SUMMARY

The `hotel_orchestrateur` pipeline currently executes inside a synchronous blocking HTTP request taking 3–5 minutes, stalling the uvicorn event loop and providing no user-facing progress. This change introduces an async run model (`POST /{id}/runs` → 202 Accepted), a lightweight state machine (`pipeline_runner`), SSE-based progression events, and a DAG execution model allowing `mobility` and `weather` stages to run in parallel. The existing `POST /{id}/chat` endpoint remains fully functional.

---

## 2. CONTEXT

### 2.1 Current State Snapshot

- `POST /{id}/chat` triggers the full pipeline synchronously; handler blocks for 3–5 minutes.
- `pipeline_executor.py` invokes tool callbacks synchronously, blocking the event loop.
- Timeouts are inconsistent: MCP=30s, stage=90s, API=120s, LLM synthesis=35s — no unified per-stage contract.
- No progress feedback is surfaced to the client during execution.
- `discover → mobility → weather → budget_fit` stages run strictly sequentially even though `mobility` and `weather` have no inter-dependency.
- `agent_factory.py` calls `probe_fn` on every hot-path request, adding latency.

### 2.2 Pain Points / Gaps

- Blocking event loop prevents concurrent request handling (scalability bottleneck).
- Inconsistent timeouts cause unpredictable failure modes.
- Users have no visibility into pipeline progress (poor UX).
- Sequential execution wastes wall-clock time for parallelisable stages.
- `probe_fn` adds unnecessary latency to each request.

---

## 3. PROBLEM STATEMENT

The current synchronous pipeline execution model is incompatible with production-grade reliability and user experience requirements. It blocks server resources, exposes clients to opaque long-wait responses, and prevents meaningful per-stage error isolation. The architecture must evolve to an async job + event-streaming model with a DAG execution strategy.

---

## 4. GOALS

1. Decouple pipeline execution from the HTTP request via an async job model.
2. Stream real-time per-stage progress to clients via SSE.
3. Enforce effective, isolated per-stage timeouts that do not cascade failures.
4. Reduce total pipeline wall-clock time by parallelising independent stages (`mobility` ∥ `weather`).
5. Maintain full backward compatibility on `POST /{id}/chat`.
6. Remove `probe_fn` from the hot request path.

### 4.1 Success Metrics / KPIs

| Metric | Target |
|--------|--------|
| `POST /{id}/runs` response time | < 500 ms (202 Accepted) |
| SSE events emitted per run | ≥ 2 per stage (started + completed/failed) |
| Wall-clock reduction for parallel stages | ≥ 30% vs sequential baseline |
| `POST /{id}/chat` compatibility | 100% — no regression on existing behaviour |
| Hot-path `probe_fn` calls | 0 per request |

### 4.2 Non-Goals

- Full frontend refactor (separate backlog item).
- Persistent run storage in a relational database (in-memory or Redis sufficient for v1).
- Modification of LLM models or agent prompts.
- Distributed task queue (e.g. Celery, ARQ) — asyncio suffices for v1.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capability | Rationale |
|----|-----------|-----------|
| F-1 | Submit pipeline run asynchronously via `POST /{id}/runs`, receive `run_id` and resource URLs immediately | Decouples client from execution duration; enables 202 Accepted pattern |
| F-2 | Poll run status and final result via `GET /{id}/runs/{run_id}` | Allows stateless clients to retrieve outcome without SSE |
| F-3 | Subscribe to real-time stage progress via SSE on `GET /{id}/runs/{run_id}/events` | Provides UX feedback; enables partial output display |
| F-4 | Execute `mobility` and `weather` stages in parallel (DAG Stage 2) | Reduces wall-clock time for independent stages |
| F-5 | Enforce isolated per-stage timeouts; a timed-out stage produces a stage-level error without aborting other stages | Improves resilience and predictability |
| F-6 | Cache `list_tools` result in `agent_factory`; remove `probe_fn` from hot path | Eliminates per-request overhead |
| F-7 | Each stage job operates on an isolated agent instance (no shared mutable state) | Required due to AgentScope ReActAgent not being thread-safe |

### 5.1 Capability Details

**F-1 — Async Run Submission**
- New endpoint returns `{ run_id, status_url, events_url }` within < 500 ms.
- Run state machine: `PENDING → RUNNING → COMPLETED | FAILED | CANCELLED`.
- `run_id` scoped to in-memory store (or Redis) for v1.

**F-3 — SSE Progression**
- Event schema (per stage): `{ stage, status: started|completed|failed, output?, error?, ts }`.
- Terminal event: `{ type: "run_complete", status, result? }`.
- Transport: `StreamingResponse` + `asyncio.Queue` per run.

**F-4 — DAG Execution**
```
Stage 1: discover
Stage 2: mobility ∥ weather   ← asyncio.gather
Stage 3: budget_fit
```

**F-5 — Per-Stage Timeouts**
- Each stage wrapped with `asyncio.wait_for(stage_coroutine, timeout=<stage_timeout>)`.
- On `asyncio.TimeoutError`: emit SSE `failed` event for that stage; pipeline continues to next stage where possible.

---

## 6. USER & SYSTEM FLOWS

### Async Run Flow

```
Client                          API                         Pipeline Runner
  │                               │                               │
  │  POST /{id}/runs               │                               │
  │──────────────────────────────>│                               │
  │  202 { run_id, status_url,    │  enqueue job                  │
  │        events_url }           │──────────────────────────────>│
  │<──────────────────────────────│                               │
  │                               │                               │ Stage 1: discover
  │  GET /runs/{run_id}/events    │                               │ Stage 2: mobility ∥ weather
  │──────────────────────────────>│   SSE stream                  │ Stage 3: budget_fit
  │   event: stage started        │<──────────────────────────────│
  │   event: stage completed      │                               │
  │   event: run_complete         │                               │
  │<──────────────────────────────│                               │
  │                               │                               │
  │  GET /runs/{run_id}           │                               │
  │──────────────────────────────>│                               │
  │  200 { status, result }       │                               │
  │<──────────────────────────────│                               │
```

### Backward-Compatible Chat Flow

```
Client
  │  POST /{id}/chat
  │──────────────────────> existing handler (unchanged)
  │  200 { response }
  │<──────────────────────
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- New REST endpoints: `POST /{id}/runs`, `GET /{id}/runs/{run_id}`, `GET /{id}/runs/{run_id}/events`.
- `pipeline_runner` service: async job lifecycle + state machine + SSE event emission.
- `pipeline_executor` refactor: DAG execution, per-stage timeout isolation, lazy-init.
- `agent_factory` optimisation: remove `probe_fn` from hot path, cache `list_tools`.
- In-memory run store (or Redis adapter interface) for `run_id` → state mapping.

### 7.2 Out of Scope

- [OUT] Full frontend refactor.
- [OUT] Persistent run history in a relational database.
- [OUT] LLM model or prompt changes.
- [OUT] Distributed task queue infrastructure.
- [OUT] Authentication / authorisation changes.

### 7.3 Deferred / Maybe-Later

- Run cancellation via `DELETE /{id}/runs/{run_id}`.
- Run list endpoint `GET /{id}/runs`.
- Redis-backed run store (v2).
- Frontend SSE integration (tracked separately).

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

| ID | Method | Path | Request | Response | Notes |
|----|--------|------|---------|----------|-------|
| API-1 | POST | `/api/agents/{id}/runs` | `{ message, context? }` | `202 { run_id, status_url, events_url }` | Immediate; < 500 ms |
| API-2 | GET | `/api/agents/{id}/runs/{run_id}` | — | `200 { run_id, status, result?, stages[] }` | Poll for final state |
| API-3 | GET | `/api/agents/{id}/runs/{run_id}/events` | — | SSE stream (text/event-stream) | Per-stage events + terminal |

### 8.2 Events / Messages

| ID | Event | Payload | Trigger |
|----|-------|---------|---------|
| EVT-1 | `stage_started` | `{ stage, ts }` | Stage begins execution |
| EVT-2 | `stage_completed` | `{ stage, output, ts }` | Stage finishes successfully |
| EVT-3 | `stage_failed` | `{ stage, error, ts }` | Stage times out or errors |
| EVT-4 | `run_complete` | `{ status: completed\|failed, result?, ts }` | All stages done |

### 8.3 Data Model Impact

| ID | Element | Change |
|----|---------|--------|
| DM-1 | `RunRecord` | New: `run_id`, `agent_id`, `status`, `stages[]`, `result`, `created_at`, `updated_at` |
| DM-2 | `StageRecord` | New: `stage_name`, `status`, `output`, `error`, `started_at`, `completed_at` |

### 8.4 External Integrations

- **AgentScope ReActAgent**: Each stage must instantiate a dedicated, isolated agent instance (not thread-safe).
- **FastAPI `StreamingResponse`**: SSE transport via `asyncio.Queue` per active run.

### 8.5 Backward Compatibility

- `POST /{id}/chat` remains unchanged in signature and behaviour.
- No breaking change to existing API consumers.

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-1 | Latency | `POST /{id}/runs` P99 ≤ 500 ms |
| NFR-2 | Concurrency | System MUST handle ≥ 10 concurrent runs without event loop starvation |
| NFR-3 | Timeout isolation | A stage timeout MUST NOT propagate cancellation to sibling or subsequent stages |
| NFR-4 | SSE reliability | SSE connection drops MUST NOT corrupt run state; client reconnect MUST recover last known state via `GET /{id}/runs/{run_id}` |
| NFR-5 | Memory | In-memory run store MUST evict completed runs after ≥ 1 h TTL to bound memory growth |
| NFR-6 | Thread safety | No shared mutable state between concurrent stage coroutines; each stage uses its own agent instance |
| NFR-7 | Backward compat | `POST /{id}/chat` regression rate = 0% |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

- Structured log entry per stage lifecycle event (started, completed, failed) including `run_id`, `stage`, `duration_ms`, `status`.
- Log final run outcome with total duration.
- SSE event timestamps (`ts`) MUST be ISO-8601 UTC.
- Error details in `stage_failed` events MUST be sanitised (no PII, no stack traces to client).

---

## 11. RISKS & MITIGATIONS

| ID | Risk | Impact | Probability | Mitigation | Residual Risk |
|----|------|--------|-------------|-----------|---------------|
| RSK-1 | AgentScope ReActAgent shared state causes data races under parallel execution | H | H | Mandate one agent instance per stage job (F-7); document as architectural constraint | Low |
| RSK-2 | SSE connections held open cause file-descriptor exhaustion under high load | M | M | Implement per-run connection timeout; evict stale SSE queues | Low |
| RSK-3 | In-memory run store lost on process restart | M | L | Accept for v1; document as known limitation; Redis adapter deferred to v2 | Medium |
| RSK-4 | `asyncio.gather` partial failure handling incorrect, causing silent data loss in DAG Stage 2 | H | M | Use `return_exceptions=True`; explicitly check each result for exception type | Low |
| RSK-5 | `POST /{id}/chat` regression introduced during refactor | H | L | Regression test suite covering existing chat behaviour; CI gate | Low |

---

## 12. ASSUMPTIONS

- GH-16 (timeout fix) is already merged and deployed; this change builds on that baseline.
- AgentScope ReActAgent is confirmed not thread-safe — isolation is mandatory, not optional.
- In-memory run store is acceptable for v1 (no persistence SLA).
- The client (frontend or API consumer) can handle SSE or fall back to polling `GET /runs/{run_id}`.
- uvicorn runs in a single-process asyncio context (no multi-worker shared state required for v1).

---

## 13. DEPENDENCIES

| Dependency | Type | Status | Notes |
|-----------|------|--------|-------|
| GH-16 (timeout fix) | Internal | ✅ Delivered | Required baseline for consistent timeout behaviour |
| FastAPI `StreamingResponse` | External | Available | SSE transport mechanism |
| AgentScope ReActAgent | External | Available | Must be instantiated per stage |
| asyncio (stdlib) | External | Available | Concurrency and timeout primitives |

---

## 14. OPEN QUESTIONS

| ID | Question | Owner | Due |
|----|----------|-------|-----|
| OQ-1 | Should `run_id` be a UUID or a shorter opaque token? Impact on URL length and log readability. | mbensass | Before implementation |
| OQ-2 | What is the acceptable TTL for run records in the in-memory store before eviction? | mbensass | Before implementation |
| OQ-3 | Should `POST /{id}/chat` internally delegate to the new async job (with a synchronous wait), or remain a fully separate code path? Decision needed: consult `@architect` | — | Before plan sign-off |
| OQ-4 | Is Redis available in the deployment environment, or is pure in-memory the only v1 option? | mbensass | Before implementation |

---

## 15. DECISION LOG

| ID | Decision | Rationale | Date |
|----|----------|-----------|------|
| DEC-1 | Use `asyncio.Queue` per run for SSE transport rather than a pub-sub broker | Keeps v1 simple; no external infrastructure dependency; sufficient for single-process deployment | 2026-04-27 |
| DEC-2 | DAG Stage 2 (`mobility` ∥ `weather`) via `asyncio.gather(return_exceptions=True)` | Native asyncio; no additional dependency; explicit exception handling required per result | 2026-04-27 |
| DEC-3 | Introduce `pipeline_runner` as a new service module rather than extending `pipeline_executor` | Separation of concerns: executor owns DAG logic; runner owns job lifecycle and state machine | 2026-04-27 |
| DEC-4 | In-memory run store for v1; Redis adapter interface deferred | Avoid premature infrastructure complexity; v1 scope does not require cross-process run sharing | 2026-04-27 |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

| Component | Nature of Change |
|-----------|-----------------|
| Agents API router | Add 3 new `/runs` endpoints (API-1, API-2, API-3) |
| `pipeline_executor` | Refactor to DAG model; add per-stage timeout isolation; lazy-init |
| `agent_factory` | Remove `probe_fn` from hot path; cache `list_tools` result |
| `pipeline_runner` (new) | Async job lifecycle, state machine, SSE queue management |
| In-memory run store (new) | `run_id` → `RunRecord` mapping with TTL eviction |

---

## 17. ACCEPTANCE CRITERIA

| ID | Criterion |
|----|-----------|
| AC-F1-1 | **Given** a valid agent `{id}` and message payload, **When** `POST /api/agents/{id}/runs` is called, **Then** the API returns `202 Accepted` with `{ run_id, status_url, events_url }` in ≤ 500 ms |
| AC-F2-1 | **Given** a completed run, **When** `GET /api/agents/{id}/runs/{run_id}` is called, **Then** the response contains `status: completed` and the final `result` |
| AC-F3-1 | **Given** an active run, **When** a client connects to `GET /api/agents/{id}/runs/{run_id}/events`, **Then** the client receives at least one `stage_started` and one `stage_completed` or `stage_failed` SSE event per stage, followed by a `run_complete` event |
| AC-F4-1 | **Given** a pipeline run, **When** Stage 2 executes, **Then** `mobility` and `weather` stages are initiated concurrently and the combined Stage 2 wall-clock duration is ≤ `max(mobility_duration, weather_duration) + 200ms` overhead |
| AC-F5-1 | **Given** the `mobility` stage times out, **When** Stage 2 executes, **Then** `weather` still completes normally and `budget_fit` (Stage 3) still executes |
| AC-F6-1 | **Given** a hot-path request to any `/runs` endpoint, **When** the request is processed, **Then** `probe_fn` is not invoked (verifiable via log absence) |
| AC-F7-1 | **Given** parallel stage execution in Stage 2, **When** both stages run concurrently, **Then** each stage operates on a distinct agent instance with no shared mutable state |
| AC-NFR7-1 | **Given** the existing `POST /{id}/chat` endpoint, **When** called with any previously-valid payload, **Then** it returns the same response structure and semantics as before this change |

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

- New `/runs` endpoints are additive; existing `POST /{id}/chat` unchanged — no feature flag required.
- Deploy as a standard release; monitor structured logs for stage lifecycle events in first 24h.
- SSE endpoint can be disabled at the router level without affecting polling fallback.

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

N/A — no persistent data store changes in v1. In-memory run records are ephemeral.

---

## 20. PRIVACY / COMPLIANCE REVIEW

- `stage_failed` SSE events MUST NOT include raw exception stack traces or user PII.
- `run_id` MUST NOT encode agent configuration or user identity.
- Run records stored in-memory are ephemeral and evicted after TTL — no GDPR persistence concern for v1.

---

## 21. SECURITY REVIEW HIGHLIGHTS

- SSE endpoint should be protected by the same authentication middleware as other agent endpoints.
- `run_id` should be unguessable (UUID v4 or equivalent entropy) to prevent enumeration.
- No new external network calls introduced by this change beyond those already made by pipeline stages.

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- New structured log fields (`run_id`, `stage`, `duration_ms`) should be indexed in the log aggregation platform.
- In-memory run store TTL eviction should be monitored; alert if store size exceeds a configurable threshold.
- `pipeline_runner` adds a new service boundary — failure modes (queue full, stage exception) should be documented in the runbook.

---

## 23. GLOSSARY

| Term | Definition |
|------|-----------|
| Run | A single async execution of the full pipeline for a given agent and input message |
| Stage | A discrete unit of pipeline work (e.g., `discover`, `mobility`, `weather`, `budget_fit`) |
| DAG | Directed Acyclic Graph — the execution topology of pipeline stages |
| SSE | Server-Sent Events — HTTP-based unidirectional event streaming (text/event-stream) |
| `probe_fn` | A function previously called on each request to verify agent tool availability; removed from hot path |
| Hot path | The request-handling code executed synchronously within an HTTP request handler |
| State machine | The lifecycle model for a run: PENDING → RUNNING → COMPLETED \| FAILED \| CANCELLED |

---

## 24. APPENDICES

### A. DAG Execution Model

```
┌─────────────┐
│  discover   │  Stage 1
└──────┬──────┘
       │
  ┌────┴────┐
  ▼         ▼
mobility  weather    Stage 2 (parallel)
  │         │
  └────┬────┘
       │
┌──────▼──────┐
│ budget_fit  │  Stage 3
└─────────────┘
```

### B. SSE Event Schema

```json
{ "event": "stage_started",   "data": { "stage": "mobility", "ts": "2026-04-27T10:00:00Z" } }
{ "event": "stage_completed", "data": { "stage": "mobility", "output": "...", "ts": "2026-04-27T10:00:45Z" } }
{ "event": "stage_failed",    "data": { "stage": "weather",  "error": "timeout", "ts": "2026-04-27T10:00:90Z" } }
{ "event": "run_complete",    "data": { "status": "completed", "result": "...", "ts": "2026-04-27T10:01:30Z" } }
```

---

## 25. DOCUMENT HISTORY

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 2026-04-27 | mbensass | Initial Proposed spec from planning session |

---

## AUTHORING GUIDELINES

- Use stable ID prefixes (`F-`, `AC-`, `NFR-`, `RSK-`, `OQ-`, `DEC-`, `API-`, `EVT-`, `DM-`) for traceability.
- Acceptance Criteria MUST use Given/When/Then format and reference at least one capability or NFR ID.
- NFRs MUST include measurable thresholds.
- Risks MUST include Impact, Probability (H/M/L), Mitigation, and Residual Risk.
- No implementation tasks, file paths, or code-level instructions in this document.
- All open architectural decisions MUST be captured as OQ entries with note: "Decision needed: consult `@architect`".

---

## VALIDATION CHECKLIST

- [x] `change.ref` matches `GH-17`
- [x] `owners` has at least one entry
- [x] `status` is "Proposed"
- [x] Section order follows spec structure
- [x] All ID prefixes unique within category
- [x] Acceptance Criteria use Given/When/Then and reference capability/NFR IDs
- [x] NFRs include measurable values
- [x] Risks include Impact & Probability
- [x] No implementation file paths or code tasks present
- [x] Only spec file to be staged and committed
