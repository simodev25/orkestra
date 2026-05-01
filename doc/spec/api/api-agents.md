---
id: API-agents
status: Current
version: 1.0.0
last_updated: 2026-05-01
links:
  related_changes:
    - GH-25
  related_features:
    - SPEC-namespace-foundation
---

# API: Agents (Registry and Retrieval)

## Overview

The `/api/agents` family of endpoints enables registration, retrieval, and management of agent definitions. As of v1.0.0, all agent operations are namespace-scoped via the optional `X-Namespace` HTTP header.

## Namespace Context

All agent endpoints resolve namespace context from the **`X-Namespace` HTTP header**:

```
X-Namespace: team-alpha
```

**Resolution behavior**:
- **Header present with valid slug**: Operations are scoped to the specified namespace
- **Header absent or empty**: Operations are scoped to the "default" namespace
- **Header contains unknown slug**: Returns HTTP 404 with `{"detail": "Namespace not found"}`

This enables logical isolation of agent definitions across teams while maintaining backward compatibility for clients that do not send the header.

---

## Endpoints

### GET /api/agents

List all agents in the resolved namespace.

**Headers**:
- `X-Namespace` (string, optional): Namespace slug (defaults to "default" if absent)

**Query Parameters**:
- `limit` (integer, optional, default: 50): Maximum number of results
- `offset` (integer, optional, default: 0): Number of results to skip
- Additional filtering parameters per implementation

**Response** (HTTP 200 OK):
```json
[
  {
    "id": "string",
    "name": "string",
    "namespace_id": "uuid-string",
    "family_id": "string",
    "purpose": "string",
    "description": "string | null",
    "status": "string",
    "version": "string",
    "created_at": "ISO-8601 UTC",
    "updated_at": "ISO-8601 UTC"
  }
]
```

**Scoping behavior**: Only agents where `namespace_id` matches the resolved namespace are returned.

**Error Responses**:
- `400 Bad Request`: Invalid query parameters
- `404 Not Found`: Namespace slug in `X-Namespace` header does not exist

---

### GET /api/agents/{id}

Retrieve a single agent by ID, scoped to the resolved namespace.

**Path Parameters**:
- `id` (string, required): Agent ID

**Headers**:
- `X-Namespace` (string, optional): Namespace slug (defaults to "default" if absent)

**Response** (HTTP 200 OK):
```json
{
  "id": "string",
  "name": "string",
  "namespace_id": "uuid-string",
  "family_id": "string",
  "purpose": "string",
  "description": "string | null",
  "selection_hints": "object | null",
  "allowed_mcps": "array | null",
  "forbidden_effects": "array | null",
  "status": "string",
  "version": "string",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC"
}
```

**Scoping behavior**: If the agent exists but its `namespace_id` does not match the resolved namespace, returns HTTP 404 (agent not visible in the requested namespace context).

**Error Responses**:
- `404 Not Found`: Agent not found, or agent exists but is in a different namespace, or namespace slug in header does not exist

---

### POST /api/agents

Create a new agent in the resolved namespace.

**Headers**:
- `X-Namespace` (string, optional): Namespace slug (defaults to "default" if absent)

**Request Body** (`application/json`):
```json
{
  "id": "string (required)",
  "name": "string (required)",
  "family_id": "string (required)",
  "purpose": "string (required)",
  "description": "string (optional)",
  "selection_hints": "object (optional)",
  "allowed_mcps": "array (optional)",
  "forbidden_effects": "array (optional)",
  "status": "string (optional, default: draft)",
  "version": "string (optional, default: 1.0.0)"
}
```

**Response** (HTTP 201 Created):
Returns the created agent with the same structure as `GET /api/agents/{id}`.

**Scoping behavior**: The created agent's `namespace_id` is set to the resolved namespace from the `X-Namespace` header (or "default" if absent).

**Error Responses**:
- `400 Bad Request`: Invalid payload
- `404 Not Found`: Namespace slug in `X-Namespace` header does not exist
- `409 Conflict`: Agent with given ID already exists

---

### PUT /api/agents/{id}

Update an existing agent, scoped to the resolved namespace.

**Path Parameters**:
- `id` (string, required): Agent ID

**Headers**:
- `X-Namespace` (string, optional): Namespace slug (defaults to "default" if absent)

**Request Body** (`application/json`):
Partial update payload (same fields as POST, all optional).

**Response** (HTTP 200 OK):
Returns the updated agent.

**Scoping behavior**: Only agents in the resolved namespace can be updated. If the agent exists in a different namespace, returns HTTP 404.

**Error Responses**:
- `400 Bad Request`: Invalid payload
- `404 Not Found`: Agent not found in resolved namespace, or namespace slug does not exist

---

### DELETE /api/agents/{id}

Delete an agent, scoped to the resolved namespace.

**Path Parameters**:
- `id` (string, required): Agent ID

**Headers**:
- `X-Namespace` (string, optional): Namespace slug (defaults to "default" if absent)

**Response** (HTTP 204 No Content):
Empty response body on successful deletion.

**Scoping behavior**: Only agents in the resolved namespace can be deleted.

**Error Responses**:
- `404 Not Found`: Agent not found in resolved namespace, or namespace slug does not exist

---

## Backward Compatibility

**Pre-v1.0.0 clients** that do not send the `X-Namespace` header continue to work unchanged:
- All operations are scoped to the "default" namespace
- Response schemas are unchanged
- No breaking changes to existing API contracts

**Migration guarantee**: All agents existing before v1.0.0 were migrated to the "default" namespace, ensuring existing clients see the same agents as before.

## Security

- All endpoints require the same authentication middleware as other platform endpoints
- Agent visibility is scoped by namespace, providing logical isolation
- No RBAC or permission enforcement in v1.0.0 (all namespaces globally readable)

## Orchestrator Constraint

When creating orchestration plans with `pipeline_agent_ids`, all referenced agents must belong to the **same namespace**. Cross-namespace pipeline agent references are rejected with HTTP 422.

## Performance Targets

- Agent list queries use an index on `namespace_id` to prevent full-table scans
- Namespace resolution overhead: ≤ 5ms P99 per request

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-05-01 | Added namespace scoping via X-Namespace header; all agents assigned to namespaces (GH-25) |
