---
id: DATA-namespace-scoping
status: Current
version: 1.0.0
last_updated: 2026-05-01
links:
  related_changes:
    - GH-25
  related_features:
    - SPEC-namespace-foundation
---

# Data Model: Namespace Scoping

## Overview

This document describes the data model changes introduced by the namespace foundation feature. Namespace scoping applies **only to `AgentDefinition` entities**. All other platform entities remain global shared resources.

---

## Namespace Entity

### Table: `namespaces`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID (VARCHAR 36) | PRIMARY KEY | Unique namespace identifier |
| `name` | VARCHAR(128) | NOT NULL, UNIQUE | Human-readable display name |
| `slug` | VARCHAR(63) | NOT NULL, UNIQUE | URL-safe identifier (pattern: `^[a-z0-9-]{1,63}$`) |
| `description` | TEXT | NULL | Optional free-text description |
| `created_at` | TIMESTAMP | NOT NULL | Record creation timestamp (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL | Last modification timestamp (UTC) |

**Indexes**:
- Primary key on `id`
- Unique constraint on `name`
- Unique constraint on `slug`

**Special Records**:
- **"default" namespace**: Seeded during migration with a fixed deterministic UUID (`DEFAULT_NAMESPACE_ID`). Protected from deletion.

**Lifecycle**:
- Created via `POST /api/namespaces`
- Updated via `PUT /api/namespaces/{slug}` (slug is immutable)
- Deleted via `DELETE /api/namespaces/{slug}` (only if no agents reference it, and not "default")

---

## AgentDefinition Enhancement

### Table: `agent_definitions`

**New Column**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `namespace_id` | VARCHAR(36) | NOT NULL, FK → `namespaces.id` | Namespace to which this agent belongs |

**New Index**:
- `ix_agent_definitions_namespace_id` on `namespace_id` (improves namespace-scoped query performance)

**Foreign Key**:
```sql
FOREIGN KEY (namespace_id) REFERENCES namespaces(id)
```

**Default Value**:
- ORM-level default: `DEFAULT_NAMESPACE_ID` (ensures new agents without explicit namespace go to "default")

**Migration Back-Fill**:
- All pre-existing `AgentDefinition` rows were updated to set `namespace_id = DEFAULT_NAMESPACE_ID` during the v1.0.0 migration.
- Post-migration invariant: `COUNT(*) WHERE namespace_id IS NULL` must equal 0.

**Relationship**:
- SQLAlchemy relationship: `AgentDefinition.namespace` → `Namespace`
- Inverse: `Namespace.agents` → list of `AgentDefinition`

---

## Global Shared Resources (No Namespace Scoping)

The following entities **do NOT have `namespace_id`** and remain globally accessible:

### Definition Entities

- **`mcp_definitions`**: MCP definitions are shared across all namespaces
- **`family_definitions`**: Agent families are global platform primitives
- **`skill_definitions`**: Skills are global and reusable across namespaces
- **`workflow_definitions`**: Workflows are global orchestration templates

### Execution Entities

- **`requests`**: Execution requests are global
- **`cases`**: Cases are global
- **`orchestration_plans`**: Plans are global execution records
- **`runs`**: Run records are global

**Rationale**: These entities represent shared platform capabilities, workflow state, and execution history that must remain accessible across all namespace boundaries. Scoping them would fragment the platform's core execution model.

---

## Migration Summary

**Migration File**: `migrations/versions/022_namespaces_foundation.py`

**Steps**:
1. Create `namespaces` table with all columns and constraints
2. Seed the "default" namespace (fixed UUID)
3. Add `namespace_id` column to `agent_definitions` as nullable FK
4. Back-fill all existing `agent_definitions` rows to `DEFAULT_NAMESPACE_ID`
5. Alter `namespace_id` to `NOT NULL`
6. Create index `ix_agent_definitions_namespace_id`

**Idempotence**: The migration uses `ON CONFLICT (slug) DO NOTHING` for the seed insert, making it safe to re-run.

**Rollback**: Downgrade removes `namespace_id` column and drops `namespaces` table.

---

## Referential Integrity Rules

1. **Namespace deletion**: Blocked if any `AgentDefinition` rows reference the namespace (enforced by service layer via HTTP 409)
2. **"default" namespace**: Protected from deletion by service layer logic
3. **Agent creation**: Must reference a valid `namespace_id` (FK constraint enforced by database)
4. **Orphaned agents**: Impossible due to `NOT NULL` constraint and FK constraint

---

## Query Patterns

### List agents by namespace

```sql
SELECT * FROM agent_definitions WHERE namespace_id = :resolved_namespace_id;
```

**Index coverage**: `ix_agent_definitions_namespace_id` ensures efficient lookup.

### Validate all pipeline agents are in the same namespace

```python
agent_ids = ["agent-1", "agent-2", "agent-3"]
agents = session.execute(
    select(AgentDefinition.namespace_id)
    .where(AgentDefinition.id.in_(agent_ids))
).all()

# Check all namespace_ids are identical
namespace_ids = {agent.namespace_id for agent in agents}
if len(namespace_ids) > 1:
    raise ValidationError("All pipeline agents must belong to the same namespace")
```

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-05-01 | Initial release: namespace entity, agent_definitions.namespace_id, migration (GH-25) |
