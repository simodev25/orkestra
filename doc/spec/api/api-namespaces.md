---
id: API-namespaces
status: Current
version: 1.0.0
last_updated: 2026-05-01
links:
  related_changes:
    - GH-25
  related_features:
    - SPEC-namespace-foundation
---

# API: Namespaces

## Overview

The `/api/namespaces` family of endpoints enables lifecycle management for namespace entities, which provide logical grouping boundaries for agent definitions.

## Endpoints

### POST /api/namespaces

Create a new namespace.

**Request Body** (`application/json`):
```json
{
  "name": "string (required, max 128 chars, unique)",
  "slug": "string (required, pattern: ^[a-z0-9-]{1,63}$, unique, immutable)",
  "description": "string (optional)"
}
```

**Response** (HTTP 201 Created):
```json
{
  "id": "uuid-string",
  "name": "string",
  "slug": "string",
  "description": "string | null",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid payload (malformed JSON, missing required fields, slug regex violation)
- `409 Conflict`: Namespace with given slug already exists

---

### GET /api/namespaces

List all namespaces with pagination support.

**Query Parameters**:
- `limit` (integer, optional, default: 50): Maximum number of results to return
- `offset` (integer, optional, default: 0): Number of results to skip

**Response** (HTTP 200 OK):
```json
[
  {
    "id": "uuid-string",
    "name": "string",
    "slug": "string",
    "description": "string | null",
    "created_at": "ISO-8601 UTC",
    "updated_at": "ISO-8601 UTC"
  }
]
```

**Error Responses**:
- `400 Bad Request`: Invalid query parameters

---

### GET /api/namespaces/{slug}

Retrieve a single namespace by its slug.

**Path Parameters**:
- `slug` (string, required): Namespace slug

**Response** (HTTP 200 OK):
```json
{
  "id": "uuid-string",
  "name": "string",
  "slug": "string",
  "description": "string | null",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC"
}
```

**Error Responses**:
- `404 Not Found`: No namespace with the given slug exists

---

### PUT /api/namespaces/{slug}

Update namespace name and/or description. The slug is immutable and cannot be changed.

**Path Parameters**:
- `slug` (string, required): Namespace slug

**Request Body** (`application/json`):
```json
{
  "name": "string (optional, max 128 chars, unique)",
  "description": "string (optional)"
}
```

**Response** (HTTP 200 OK):
```json
{
  "id": "uuid-string",
  "name": "string",
  "slug": "string",
  "description": "string | null",
  "created_at": "ISO-8601 UTC",
  "updated_at": "ISO-8601 UTC"
}
```

**Error Responses**:
- `400 Bad Request`: Invalid payload
- `404 Not Found`: No namespace with the given slug exists
- `409 Conflict`: New name conflicts with an existing namespace

---

### DELETE /api/namespaces/{slug}

Delete a namespace. Deletion is only permitted if:
1. No `AgentDefinition` rows reference the namespace
2. The namespace is not the protected "default" namespace

**Path Parameters**:
- `slug` (string, required): Namespace slug

**Response** (HTTP 204 No Content):
Empty response body on successful deletion.

**Error Responses**:
- `404 Not Found`: No namespace with the given slug exists
- `409 Conflict`: Namespace is referenced by one or more agents, or is the protected "default" namespace

---

## Request Header: X-Namespace

Agent-related endpoints support an optional `X-Namespace` header to establish namespace context:

```
X-Namespace: team-alpha
```

**Behavior**:
- **Header present**: Resolves to the namespace with the given slug
- **Header absent or empty**: Resolves to the "default" namespace
- **Unknown slug**: Returns HTTP 404 with `{"detail": "Namespace not found"}`

**Affected Endpoints**:
- `GET /api/agents`: Returns only agents in the resolved namespace
- `GET /api/agents/{id}`: Returns 404 if agent exists in a different namespace
- `POST /api/agents`: Creates agent in the resolved namespace

## Security

- All endpoints require the same authentication middleware as other platform endpoints
- Slug validation regex (`^[a-z0-9-]{1,63}$`) prevents injection attacks
- No authorization/RBAC enforcement in this version (all namespaces globally readable)

## Performance Targets

- **CRUD endpoints**: P50 < 50ms, P95 < 200ms under 50 concurrent requests
- **Namespace resolution overhead**: ≤ 5ms P99 per request

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-05-01 | Initial release: namespace CRUD endpoints and X-Namespace header resolution (GH-25) |
