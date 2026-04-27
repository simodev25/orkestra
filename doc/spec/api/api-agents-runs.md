---
id: API-agents-runs
status: Current
version: 0.2.0
last_updated: 2026-04-28
links:
  related_changes:
    - GH-17
  related_features:
    - SPEC-async-pipeline-execution
---

# API: Async Pipeline Runs

## Overview

The `/api/agents/{id}/runs` family of endpoints enables asynchronous submission, status polling, and real-time progress streaming for multi-stage pipeline executions.

## Endpoints

### POST /api/agents/{id}/runs

Submit a new async pipeline run.

**Path Parameters**:
- `id` (string, required): Agent ID

**Request Body** (`application/json`):
```json
{
  "message": "string (required)",
  "context": "string (optional)"
}
```

**Response** (HTTP 202 Accepted):
```json
{
  "run_id": "uuid-v4-string",
  "status_url": "/api/agents/{id}/runs/{run_id}",
  "events_url": "/api/agents/{id}/runs/{run_id}/events"
}
```

**Response Time**: P99 ≤ 500ms

**Error Responses**:
- `400 Bad Request`: Invalid payload
- `404 Not Found`: Agent not found

---

### GET /api/agents/{id}/runs/{run_id}

Poll run status and retrieve final result.

**Path Parameters**:
- `id` (string, required): Agent ID
- `run_id` (string, required): Run ID

**Response** (HTTP 200 OK):
```json
{
  "run_id": "uuid-v4-string",
  "agent_id": "string",
  "status": "pending | running | completed | failed | cancelled",
  "result": "string (optional, present when completed)",
  "error": "string (optional, present when failed)",
  "stages": [
    {
      "stage_name": "string",
      "status": "pending | running | completed | failed",
      "output": "string (optional)",
      "error": "string (optional, sanitized)",
      "started_at": "ISO-8601 UTC (optional)",
      "completed_at": "ISO-8601 UTC (optional)",
      "duration_ms": "integer"
    }
  ],
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC",
  "started_at": "ISO-8601 UTC (optional)",
  "completed_at": "ISO-8601 UTC (optional)"
}
```

**Error Responses**:
- `404 Not Found`: Agent or run not found
- `403 Forbidden`: Run belongs to a different agent

---

### GET /api/agents/{id}/runs/{run_id}/events

Subscribe to real-time SSE progress events.

**Path Parameters**:
- `id` (string, required): Agent ID
- `run_id` (string, required): Run ID

**Response** (HTTP 200 OK, `text/event-stream`):

SSE event stream with the following event types:

#### Event: `stage_started`
```
event: stage_started
data: {"stage": "string", "ts": "ISO-8601 UTC"}
```

#### Event: `stage_completed`
```
event: stage_completed
data: {"stage": "string", "output": "string", "ts": "ISO-8601 UTC"}
```

#### Event: `stage_failed`
```
event: stage_failed
data: {"stage": "string", "error": "sanitized error message", "ts": "ISO-8601 UTC"}
```

#### Event: `run_complete` (terminal)
```
event: run_complete
data: {"status": "completed | failed", "result": "string (optional)", "ts": "ISO-8601 UTC"}
```

**Error Handling**:
- Error payloads are sanitized (no stack traces, no PII)
- SSE disconnects do not corrupt run state
- Clients can reconnect and poll the status endpoint to recover state

**Error Responses**:
- `404 Not Found`: Agent or run not found
- `403 Forbidden`: Run belongs to a different agent

---

## Security

- All endpoints require the same authentication middleware as other agent endpoints
- `run_id` is a UUID v4 with sufficient entropy to prevent enumeration attacks
- Agent ownership is enforced: requests must match the agent_id in the run record

## Version History

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-04-28 | Initial release: async run submission, polling, SSE events (GH-17) |
