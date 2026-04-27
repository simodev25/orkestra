---
id: DOMAIN-events-catalog
status: Current
version: 0.2.0
last_updated: 2026-04-28
links:
  related_changes:
    - GH-17
---

# Domain Events Catalog

## Overview

This document catalogs the domain events emitted by the Orkestra platform. Domain events represent significant occurrences in the system's lifecycle and enable real-time observability and client-side state synchronization.

---

## Pipeline Run Events (SSE)

The async pipeline execution feature emits Server-Sent Events (SSE) to provide real-time progress updates to subscribed clients.

**Event Channel**: `GET /api/agents/{id}/runs/{run_id}/events`  
**Transport**: `text/event-stream` (SSE)  
**Introduced**: v0.2.0 (GH-17)

---

### Event: `stage_started`

Emitted when a pipeline stage begins execution.

**Event Name**: `stage_started`

**Payload** (`application/json`):
```json
{
  "stage": "string (stage name: discover | mobility | weather | budget_fit)",
  "ts": "ISO-8601 UTC timestamp"
}
```

**Example**:
```
event: stage_started
data: {"stage": "mobility", "ts": "2026-04-28T10:00:00Z"}
```

**Trigger**: Stage execution coroutine starts  
**Frequency**: Once per stage per run  
**Ordering**: Always precedes corresponding `stage_completed` or `stage_failed` event for the same stage

---

### Event: `stage_completed`

Emitted when a pipeline stage finishes successfully.

**Event Name**: `stage_completed`

**Payload** (`application/json`):
```json
{
  "stage": "string (stage name)",
  "output": "string (stage result)",
  "ts": "ISO-8601 UTC timestamp"
}
```

**Example**:
```
event: stage_completed
data: {"stage": "mobility", "output": "Public transit available: Metro Line 1 to...", "ts": "2026-04-28T10:00:45Z"}
```

**Trigger**: Stage execution coroutine completes without error or timeout  
**Frequency**: Once per successfully completed stage per run

---

### Event: `stage_failed`

Emitted when a pipeline stage times out or encounters an error.

**Event Name**: `stage_failed`

**Payload** (`application/json`):
```json
{
  "stage": "string (stage name)",
  "error": "string (sanitized error message; no stack traces, no PII)",
  "ts": "ISO-8601 UTC timestamp"
}
```

**Example**:
```
event: stage_failed
data: {"stage": "weather", "error": "Stage timeout after 90s", "ts": "2026-04-28T10:01:30Z"}
```

**Trigger**: Stage execution coroutine raises exception or exceeds timeout  
**Frequency**: Once per failed stage per run  
**Privacy/Security**: Error messages are sanitized; raw exception stack traces are never exposed to clients

---

### Event: `run_complete` (Terminal)

Emitted when the entire pipeline run reaches a terminal state (`completed` or `failed`).

**Event Name**: `run_complete`

**Payload** (`application/json`):
```json
{
  "status": "completed | failed",
  "result": "string (optional; aggregated final result when status=completed)",
  "ts": "ISO-8601 UTC timestamp"
}
```

**Example (success)**:
```
event: run_complete
data: {"status": "completed", "result": "Best hotel: Grand Palace (fits budget, accessible via Metro, sunny forecast)", "ts": "2026-04-28T10:02:00Z"}
```

**Example (failure)**:
```
event: run_complete
data: {"status": "failed", "ts": "2026-04-28T10:02:00Z"}
```

**Trigger**: All stages have completed (successfully or with failures); final run status is determined  
**Frequency**: Once per run (terminal event)  
**Ordering**: Always the final SSE event emitted for a run

---

## Event Ordering Guarantees

Within a single run's SSE stream:
1. `stage_started` precedes `stage_completed` or `stage_failed` for the same stage
2. Stage events are emitted in DAG execution order (Stage 1 → Stage 2 → Stage 3)
3. `run_complete` is always the final event

**Note**: In Stage 2, `mobility` and `weather` execute concurrently. Their `stage_started` events may be emitted in any order, but both will precede Stage 3 events.

---

## Timestamp Format

All `ts` fields are ISO-8601 UTC timestamps in the format:
```
YYYY-MM-DDTHH:MM:SS.ffffffZ
```

Example: `2026-04-28T10:00:45.123456Z`

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial catalog: SSE pipeline run events (GH-17) |
