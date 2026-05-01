---
id: SPEC-namespace-foundation
status: Current
version: 1.0.0
last_updated: 2026-05-01
owners:
  - mbensass
links:
  related_changes:
    - GH-25
---

# Feature: Namespace Foundation — Logical Grouping for Agent Definitions

## Overview

Orkestra provides a **namespace** primitive that enables logical grouping and organizational boundaries for agent definitions. Namespaces allow teams to own and manage their agents independently while maintaining a shared platform for MCPs, skills, families, workflows, and execution entities.

## Current Behavior

### Namespace Entity

A namespace is a first-class entity with:
- **Unique identifier** (`id`): UUID primary key
- **Human-readable name**: Unique display name (max 128 characters)
- **URL-safe slug**: Immutable identifier used in HTTP headers and URLs (max 63 characters, pattern: `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$`)
- **Optional description**: Free-text field for documentation
- **Timestamps**: `created_at` and `updated_at`

### Default Namespace

The system includes a protected "default" namespace (slug: `default`) that:
- Is seeded automatically during database migration
- Receives all pre-existing agents during migration
- Serves as the fallback for requests without an explicit namespace context
- Cannot be deleted via the API

### Agent-Only Scoping

**Only `AgentDefinition` entities have namespace scoping.** Each agent belongs to exactly one namespace via a `namespace_id` foreign key with `NOT NULL` constraint.

**The following entities remain global shared resources with no namespace scoping:**
- MCP definitions
- Skill definitions
- Family definitions
- Workflow definitions
- Requests
- Cases
- Orchestration plans
- Runs

This design ensures that shared platform capabilities remain accessible across all namespaces while providing organizational boundaries for team-owned agents.

### Request-Scoped Namespace Resolution

Namespace context is resolved per-request using the **`X-Namespace` HTTP header**:

1. **Header present with valid slug**: Resolves to the specified namespace
2. **Header absent or empty**: Resolves to the "default" namespace
3. **Header contains unknown slug**: Returns HTTP 404 with `{"detail": "Namespace not found"}`

This resolution occurs in a FastAPI dependency and injects the resolved `Namespace` object into route handlers that require namespace context.

### Agent Endpoints with Namespace Filtering

Agent list and retrieval endpoints apply namespace filtering:

- **`GET /api/agents`**: Returns only agents in the resolved namespace
- **`GET /api/agents/{id}`**: Returns 404 if the agent exists but belongs to a different namespace than the resolved context

This ensures that clients with an `X-Namespace: team-alpha` header see only team-alpha agents, maintaining logical isolation.

**Backward compatibility**: Clients that do not send the `X-Namespace` header continue to work unchanged, seeing only agents in the "default" namespace.

### Orchestrator Same-Namespace Validation

When creating or validating orchestration plans with `pipeline_agent_ids`, the orchestrator enforces that all referenced agents belong to the **same namespace**:

- **All agents in same namespace**: Validation passes, plan creation proceeds
- **Agents from different namespaces**: HTTP 422 returned with message: `"All pipeline agents must belong to the same namespace"`

This prevents logical inconsistencies where orchestration plans mix agents from different teams or organizational boundaries.

### Namespace Lifecycle API

Full CRUD operations are available:

| Operation | Endpoint | Behavior |
|-----------|----------|----------|
| Create | `POST /api/namespaces` | Create new namespace; slug must be unique (409 on conflict) |
| List | `GET /api/namespaces` | List all namespaces with pagination (limit/offset) |
| Get | `GET /api/namespaces/{slug}` | Retrieve single namespace by slug |
| Update | `PUT /api/namespaces/{slug}` | Update name/description (slug is immutable) |
| Delete | `DELETE /api/namespaces/{slug}` | Hard-delete if unreferenced; 409 if any agents exist; "default" is protected |

## Data Model

### Namespace Table

```
namespaces
  id              UUID PK
  name            VARCHAR(128) UNIQUE NOT NULL
  slug            VARCHAR(63) UNIQUE NOT NULL
  description     TEXT NULL
  created_at      TIMESTAMP NOT NULL
  updated_at      TIMESTAMP NOT NULL
```

### AgentDefinition Enhancement

```
agent_definitions
  ...existing columns...
  namespace_id    VARCHAR(36) NOT NULL FK → namespaces.id
  
INDEX ix_agent_definitions_namespace_id ON (namespace_id)
```

## Migration and Data Integrity

The database migration ensures:
1. Creation of the `namespaces` table
2. Seeding of the "default" namespace with a fixed deterministic UUID
3. Addition of `namespace_id` column to `agent_definitions`
4. Back-fill of all existing agents to the default namespace
5. Enforcement of `NOT NULL` constraint on `namespace_id`
6. Creation of an index on `namespace_id` for query performance

The migration is idempotent and safe to re-run.

**Post-migration invariant**: Zero `AgentDefinition` rows have `namespace_id IS NULL`.

## Security and Access Control

**This feature provides logical grouping only, not access control.**

- All namespaces are globally readable
- No RBAC or permission enforcement is included
- Future authorization features are deferred to subsequent changes

The slug validation regex prevents injection attacks by limiting characters to lowercase alphanumeric and hyphens.

## Non-Functional Characteristics

- **Namespace resolution overhead**: ≤ 5ms P99 per request
- **CRUD endpoint latency**: P50 < 50ms, P95 < 200ms under 50 concurrent requests
- **Migration idempotence**: Safe to re-run without errors or state corruption
- **Query performance**: Indexed `namespace_id` prevents full-table scans on agent list queries

## Observability

The system logs:
- **Namespace resolution failures** (slug not found): WARNING level with requested slug
- **Namespace CRUD operations** (create/update/delete): INFO level with namespace_id
- **Orchestrator rejections** (cross-namespace pipeline_agent_ids): WARNING level with conflicting agent IDs and namespace slugs

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-05-01 | Initial release: namespace entity, agent scoping, X-Namespace resolution, orchestrator validation (GH-25) |
