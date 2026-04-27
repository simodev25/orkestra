---
id: SPEC-async-pipeline-execution
status: Current
version: 0.2.0
last_updated: 2026-04-28
owners:
  - mbensass
links:
  related_changes:
    - GH-17
---

# Feature: Async Pipeline Execution with SSE Progress Streaming

## Overview

The Orkestra platform supports asynchronous execution of multi-stage pipeline runs with real-time progress streaming via Server-Sent Events (SSE). This decouples long-running pipeline execution from the HTTP request/response cycle, enabling scalable concurrent execution and providing clients with real-time visibility into pipeline progress.

## Current Behavior

### Async Run Submission

Clients can submit a pipeline run asynchronously via `POST /api/agents/{id}/runs` with a message payload. The API immediately returns HTTP 202 Accepted with:
- A unique `run_id` (UUID v4)
- A `status_url` for polling run status
- An `events_url` for subscribing to real-time SSE events

The pipeline execution begins in the background without blocking the request handler.

**Response time target**: P99 ≤ 500ms

### Run Status Polling

Clients can poll the run status and retrieve the final result via `GET /api/agents/{id}/runs/{run_id}`. The response includes:
- Current run status (`pending`, `running`, `completed`, `failed`, `cancelled`)
- Per-stage status and outputs
- Final aggregated result (when completed)
- Timestamps (ISO-8601 UTC)

### Real-Time Progress Streaming (SSE)

Clients can subscribe to real-time stage progress via `GET /api/agents/{id}/runs/{run_id}/events`. The SSE stream emits:
- `stage_started`: when a stage begins execution
- `stage_completed`: when a stage finishes successfully
- `stage_failed`: when a stage times out or errors
- `run_complete`: terminal event indicating final run status

All timestamps are ISO-8601 UTC. Error payloads are sanitized (no stack traces, no PII).

**Resilience**: SSE disconnects do not corrupt run state. Clients can reconnect and poll the status endpoint to recover the current state.

### DAG-Based Parallel Execution

The pipeline executor implements a Directed Acyclic Graph (DAG) execution model:

```
Stage 1: discover
Stage 2: mobility ∥ weather (parallel)
Stage 3: budget_fit
```

Independent stages in Stage 2 (`mobility` and `weather`) run concurrently via `asyncio.gather`, reducing total wall-clock time by approximately 30% compared to sequential execution.

### Per-Stage Timeout Isolation

Each stage is wrapped with `asyncio.wait_for` to enforce per-stage timeouts. When a stage times out:
- The stage emits a `stage_failed` event
- Sibling stages in the same DAG level continue execution
- Subsequent stages are executed when possible
- The overall run does not cascade fail due to a single stage timeout

### Agent Isolation

Due to AgentScope ReActAgent not being thread-safe, each stage execution instantiates a dedicated, isolated agent instance. No shared mutable state exists between concurrent stage coroutines.

### Hot-Path Optimization

The agent factory no longer invokes `probe_fn` in the request hot path. MCP tool discovery results (`list_tools`) are cached with a TTL to reduce per-request overhead.

### In-Memory Run Store

Run records are stored in-memory with TTL-based eviction (default: 1800 seconds). Completed or failed runs are eligible for eviction after the TTL expires. A bounded size guardrail prevents memory exhaustion by evicting the oldest terminal runs when capacity is reached.

**v1 Limitation**: Run records are ephemeral and lost on process restart. Redis-backed persistence is deferred to v2.

## Backward Compatibility

The existing `POST /api/agents/{id}/chat` endpoint remains fully functional and unchanged. It continues to execute the pipeline synchronously within the request/response cycle and returns the full result in a single response.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agents/{id}/runs` | Submit async pipeline run (202 Accepted) |
| GET | `/api/agents/{id}/runs/{run_id}` | Poll run status and final result |
| GET | `/api/agents/{id}/runs/{run_id}/events` | Subscribe to SSE progress events |

## Run Lifecycle State Machine

```
PENDING → RUNNING → COMPLETED
                  ↘ FAILED
                  ↘ CANCELLED (future)
```

## Non-Functional Characteristics

- **Latency**: POST /runs P99 ≤ 500ms
- **Concurrency**: System handles ≥10 concurrent runs without event loop starvation
- **Timeout Isolation**: Stage timeout does not propagate to siblings or downstream stages
- **SSE Reliability**: Connection drops do not corrupt state; poll recovers last known state
- **Memory**: TTL eviction bounds memory growth; configurable max_runs guardrail
- **Thread Safety**: No shared mutable state; per-stage isolated agent instances

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial release: async run model, SSE streaming, DAG parallelism, timeout isolation (GH-17) |
