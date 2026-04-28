---
id: SPEC-nonfunctional-requirements
status: Current
version: 0.2.0
last_updated: 2026-04-28
links:
  related_changes:
    - GH-17
---

# System Non-Functional Requirements (NFRs)

## Overview

This document defines the current non-functional requirements and characteristics of the Orkestra platform.

---

## Performance

### NFR-PERF-001: Async Run Submission Latency
**Category**: Performance  
**Requirement**: `POST /api/agents/{id}/runs` P99 response time ≤ 500ms  
**Rationale**: Async submission must be fast; execution happens in background  
**Measurement**: Per-request latency tracking in production; CI integration tests (best-effort)  
**Version**: 0.2.0 (GH-17)

---

### NFR-PERF-002: DAG Parallelism Wall-Clock Reduction
**Category**: Performance  
**Requirement**: Stage 2 parallel execution reduces total wall-clock time by ≥30% compared to sequential baseline  
**Rationale**: Justify DAG model vs sequential execution  
**Measurement**: E2E timing tests comparing parallel vs sequential stage durations  
**Version**: 0.2.0 (GH-17)

---

## Scalability

### NFR-SCALE-001: Concurrent Run Capacity
**Category**: Scalability  
**Requirement**: System handles ≥10 concurrent pipeline runs without event loop starvation  
**Rationale**: Support multiple users submitting runs simultaneously  
**Measurement**: Integration test with 10 concurrent runs; production monitoring of `asyncio.active_tasks`  
**Version**: 0.2.0 (GH-17)

---

## Reliability

### NFR-REL-001: Timeout Isolation
**Category**: Reliability  
**Requirement**: A stage timeout MUST NOT propagate cancellation to sibling or subsequent stages  
**Rationale**: Isolate failures; allow partial results  
**Measurement**: E2E tests with forced stage timeout; verify sibling stage completion  
**Version**: 0.2.0 (GH-17)

---

### NFR-REL-002: SSE Connection Resilience
**Category**: Reliability  
**Requirement**: SSE connection drops MUST NOT corrupt run state; client reconnect MUST recover last known state via status endpoint  
**Rationale**: Network instability should not affect run integrity  
**Measurement**: Integration test with forced SSE disconnect; poll status endpoint for final result  
**Version**: 0.2.0 (GH-17)

---

## Resource Management

### NFR-RES-001: In-Memory Run Store TTL Eviction
**Category**: Resource Management  
**Requirement**: In-memory run store MUST evict completed runs after ≥1h TTL to bound memory growth  
**Rationale**: Prevent unbounded memory consumption  
**Measurement**: Unit tests with controllable clock; production monitoring of `orkestra_run_store_size`  
**Version**: 0.2.0 (GH-17)

---

### NFR-RES-002: Run Store Bounded Size Guardrail
**Category**: Resource Management  
**Requirement**: Run store MUST enforce a maximum capacity (default: 1000 runs); evict oldest terminal runs when capacity reached  
**Rationale**: Prevent memory exhaustion under high load  
**Measurement**: Unit tests with max_runs enforcement; production alerts on store size  
**Version**: 0.2.0 (GH-17)

---

## Thread Safety

### NFR-THREAD-001: Agent Instance Isolation
**Category**: Thread Safety  
**Requirement**: No shared mutable state between concurrent stage coroutines; each stage uses its own agent instance  
**Rationale**: AgentScope ReActAgent is not thread-safe; prevent data races  
**Measurement**: E2E tests verifying distinct agent instance IDs per stage; code review of agent factory logic  
**Version**: 0.2.0 (GH-17)

---

## Backward Compatibility

### NFR-COMPAT-001: Chat Endpoint Stability
**Category**: Backward Compatibility  
**Requirement**: `POST /api/agents/{id}/chat` regression rate = 0% (response structure and semantics unchanged)  
**Rationale**: Existing API consumers must not be affected by async run feature  
**Measurement**: Regression test suite comparing response shape/behavior to pre-change baseline  
**Version**: 0.2.0 (GH-17)

---

## Security

### NFR-SEC-001: SSE Error Sanitization
**Category**: Security / Privacy  
**Requirement**: `stage_failed` SSE events MUST NOT include raw exception stack traces or user PII  
**Rationale**: Prevent information leakage to clients  
**Measurement**: Integration tests validating error payload sanitization  
**Version**: 0.2.0 (GH-17)

---

### NFR-SEC-002: Run ID Entropy
**Category**: Security  
**Requirement**: `run_id` MUST be a UUID v4 or equivalent (≥122 bits entropy) to prevent enumeration attacks  
**Rationale**: Protect run data from unauthorized access via guessing  
**Measurement**: Code review of run ID generation; unit tests verifying UUID format  
**Version**: 0.2.0 (GH-17)

---

## Observability

### NFR-OBS-001: Structured Logging for Stage Lifecycle
**Category**: Observability  
**Requirement**: Each stage lifecycle event (started, completed, failed) MUST emit a structured log entry with `run_id`, `stage`, `duration_ms`, `status`  
**Rationale**: Enable operational troubleshooting and monitoring  
**Measurement**: Log validation in integration tests; production log aggregation queries  
**Version**: 0.2.0 (GH-17)

---

### NFR-OBS-002: ISO-8601 UTC Timestamps
**Category**: Observability  
**Requirement**: All SSE event timestamps (`ts`) and log timestamps MUST be ISO-8601 UTC  
**Rationale**: Standardize temporal data for cross-system correlation  
**Measurement**: Unit tests validating timestamp format  
**Version**: 0.2.0 (GH-17)

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial NFRs: async pipeline performance, scalability, reliability, security (GH-17) |
