---
change:
  ref: GH-25
  type: feat
  status: Proposed
  slug: namespace-foundation
  title: "Namespace Foundation — First-Class Scoping Primitive for All Registry & Execution Entities"
  owners: [mbensass]
  service: core-platform
  labels: [namespace, multi-tenancy, data-model, api, migration]
  version_impact: minor
  audience: internal
  security_impact: low
  risk_level: medium
  dependencies:
    internal: [registry-service, execution-service, orchestration-service, request-service]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Define the introduction of a `Namespace` model as the canonical scoping primitive in Orkestra. All registry and execution entities (agents, MCPs, families, skills, workflows, requests, cases, plans, runs) gain a `namespace_id` foreign-key. A request-scoped middleware propagates namespace context from the `X-Namespace` HTTP header. A CRUD API exposes namespace management. Existing data is migrated to a seed "default" namespace. `tenant_id` is preserved on Request and Case as a deprecated compatibility field.

---

## 1. SUMMARY

Orkestra currently has no logical isolation boundary between groups of entities. Every agent definition, MCP, workflow, request, and run is globally visible. The `tenant_id` field present on `Request` and `Case` is always the string "default" and provides no real scoping.

This change introduces a first-class `Namespace` model and propagates it as a `namespace_id` FK across all nine core entity models. A FastAPI dependency/middleware resolves namespace context from the `X-Namespace` request header (defaulting to "default" for backward compatibility). A REST CRUD API (`/api/namespaces`) exposes namespace lifecycle management. An Alembic migration seeds the "default" namespace, back-fills all existing rows, and enforces the FK as `NOT NULL`. No access-control or visibility policy is introduced; all namespaces remain globally visible in this iteration.

---

## 2. CONTEXT

### 2.1 Current State Snapshot

- All registry entities (`AgentDefinition`, `MCPDefinition`, `FamilyDefinition`, `SkillDefinition`, `WorkflowDefinition`) and execution entities (`Request`, `Case`, `OrchestrationPlan`, `Run`) are stored without any isolation boundary.
- `Request` and `Case` each carry a `tenant_id` column (always "default"); it is consulted by no filtering logic.
- The platform is positioned as the foundation for a multi-namespace/multi-team deployment model (epic GH-24), but no scoping primitive exists.
- FastAPI route handlers receive no namespace context; service-layer functions perform no namespace-scoped queries.

### 2.2 Pain Points / Gaps

- **No isolation boundary**: agents, MCPs, and workflows created by one team are immediately visible to all.
- **Misleading `tenant_id`**: the field implies isolation but provides none; it is a source of confusion.
- **No namespace lifecycle management**: no API to create, list, update, or deactivate namespaces.
- **No propagation mechanism**: even if a namespace column existed, no mechanism passes namespace context through the HTTP request lifecycle.

---

## 3. PROBLEM STATEMENT

Without a scoping primitive, Orkestra cannot support multi-team deployments where each team's agents, workflows, and execution history must be logically separated. Any future feature (RBAC, namespace-scoped quotas, namespace-aware audit logs) is blocked until a stable namespace identity exists on every entity and is propagated end-to-end through the request lifecycle.

---

## 4. GOALS

1. Introduce a `Namespace` entity as the canonical scoping primitive.
2. Attach `namespace_id` to all nine core models without breaking existing clients.
3. Provide a request-scoped namespace context resolved from `X-Namespace` header.
4. Expose a CRUD API for namespace lifecycle management.
5. Migrate all existing data to the "default" namespace with zero data loss.
6. Preserve `tenant_id` on `Request` and `Case` as a deprecated compatibility alias.

### 4.1 Success Metrics / KPIs

| Metric | Target |
|---|---|
| Entities without `namespace_id` after migration | 0 |
| Existing API clients broken by this change | 0 |
| Requests missing `X-Namespace` header resolved to "default" | 100 % |
| Migration duration (on representative dataset ≤ 100 k rows per table) | < 5 min |
| Namespace CRUD endpoints P95 response time | < 200 ms |

### 4.2 Non-Goals

- [OUT] Access control or permission enforcement on namespaces.
- [OUT] Namespace-scoped visibility policies (each namespace remains globally readable).
- [OUT] `tenant_id` removal (deferred to a future cleanup change).
- [OUT] Namespace quota or rate-limit enforcement.
- [OUT] UI/frontend changes for namespace selection.
- [OUT] Namespace-aware audit log filtering.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capability | Rationale |
|---|---|---|
| F-1 | Namespace entity lifecycle (create, read, update, soft-delete) | Required to manage the set of available namespaces as a first-class resource. |
| F-2 | `namespace_id` FK on all nine core models | Provides a stable, queryable isolation column on every entity. |
| F-3 | Request-scoped namespace context resolution | Enables service-layer functions to receive namespace context without caller-side plumbing. |
| F-4 | `X-Namespace` header propagation with "default" fallback | Ensures backward compatibility for existing clients sending no header. |
| F-5 | Data migration: seed "default", back-fill, enforce NOT NULL | Guarantees referential integrity on all existing rows after deployment. |
| F-6 | Deprecated `tenant_id` preservation on Request/Case | Prevents breaking changes to clients that read or write `tenant_id`. |

### 5.1 Capability Details

**F-1 — Namespace Entity**

The `Namespace` model carries: `id` (UUID PK), `name` (human-readable, unique), `slug` (URL-safe identifier, unique, immutable after creation), `description` (optional text), `owner` (string identifier of the creating principal), `created_at`, `updated_at`. Soft-delete is out of scope for this change; hard-delete is permitted only when no entities reference the namespace.

**F-2 — namespace_id FK**

Nine models receive `namespace_id UUID NOT NULL REFERENCES namespaces(id)`: `AgentDefinition`, `MCPDefinition`, `FamilyDefinition`, `SkillDefinition`, `WorkflowDefinition`, `Request`, `Case`, `OrchestrationPlan`, `Run`.

**F-3 — Request-Scoped Context**

A FastAPI dependency resolves namespace from the incoming `X-Namespace` header. If the header is absent or empty, the dependency resolves to the "default" namespace. The dependency validates that the resolved namespace exists; if not found, it returns HTTP 404. The resolved `Namespace` object is injected into route handlers that opt in.

**F-4 — Header Propagation**

The `X-Namespace` header value is treated as a namespace `slug`. The resolution logic: exact slug match → resolved; header absent → "default" slug used; slug not found → HTTP 404 (unless header absent, in which case "default" is guaranteed to exist post-migration).

**F-5 — Migration**

Alembic migration steps (single migration file):
1. Create `namespaces` table.
2. Insert the "default" namespace row (fixed UUID seed for determinism).
3. Add `namespace_id` as nullable FK to each of the nine tables.
4. `UPDATE` each table setting `namespace_id` to the "default" namespace UUID.
5. Alter `namespace_id` to `NOT NULL`.

**F-6 — tenant_id Preservation**

`tenant_id` columns on `Request` and `Case` are retained unchanged. They are marked `@deprecated` in model docstrings. No new writes by Orkestra internals use `tenant_id`; all new scoping uses `namespace_id`.

---

## 6. USER & SYSTEM FLOWS

### Flow A — Client with X-Namespace header

```
Client → POST /api/requests  [X-Namespace: team-alpha]
  → Middleware resolves slug "team-alpha" → Namespace{id: <uuid>}
  → Route handler receives namespace context
  → Request row created with namespace_id = <uuid>
  → Response 201
```

### Flow B — Legacy client without X-Namespace header

```
Client → POST /api/requests  [no X-Namespace]
  → Middleware resolves to "default" namespace
  → Request row created with namespace_id = <default-uuid>
  → Response 201  (no change in behavior for legacy client)
```

### Flow C — Namespace CRUD

```
Admin → POST /api/namespaces  {name, slug, description, owner}
  → Namespace created, 201 returned
Admin → GET  /api/namespaces        → list all namespaces
Admin → GET  /api/namespaces/{slug} → single namespace
Admin → PUT  /api/namespaces/{slug} → update name/description/owner
Admin → DELETE /api/namespaces/{slug} → hard-delete if no referenced entities
```

### Flow D — Invalid namespace slug

```
Client → GET /api/agents  [X-Namespace: nonexistent]
  → Middleware → slug lookup fails → HTTP 404 {"detail": "Namespace not found"}
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- `Namespace` SQLAlchemy async model.
- `namespace_id` FK column on nine models.
- Alembic migration (create, seed, back-fill, enforce NOT NULL).
- FastAPI dependency for request-scoped namespace context.
- REST CRUD endpoints: `GET/POST /api/namespaces`, `GET/PUT/DELETE /api/namespaces/{slug}`.
- Pydantic schemas for namespace request/response.
- Service-layer functions for namespace CRUD.
- Backward-compatible default resolution for missing `X-Namespace` header.
- Preservation of `tenant_id` as deprecated column.

### 7.2 Out of Scope

- [OUT] Access control / RBAC on namespaces.
- [OUT] Namespace-scoped filtering on existing list endpoints (deferred).
- [OUT] `tenant_id` removal.
- [OUT] Frontend/UI changes.
- [OUT] Namespace quota enforcement.
- [OUT] Namespace-aware audit logging.

### 7.3 Deferred / Maybe-Later

- Namespace-scoped filtering on all list endpoints (follow-on change in GH-24 epic).
- Soft-delete / archival of namespaces.
- Namespace ownership and RBAC.
- `tenant_id` deprecation removal after sufficient migration window.

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

| ID | Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|---|
| API-1 | POST | `/api/namespaces` | `NamespaceCreate` | `201 NamespaceRead` | Slug must be unique |
| API-2 | GET | `/api/namespaces` | — | `200 List[NamespaceRead]` | Pagination via `limit`/`offset` |
| API-3 | GET | `/api/namespaces/{slug}` | — | `200 NamespaceRead` \| `404` | Lookup by slug |
| API-4 | PUT | `/api/namespaces/{slug}` | `NamespaceUpdate` | `200 NamespaceRead` \| `404` | Slug immutable |
| API-5 | DELETE | `/api/namespaces/{slug}` | — | `204` \| `404` \| `409` | 409 if referenced entities exist |

**Schema: NamespaceCreate**
```
name: string (required, max 128)
slug: string (required, pattern: ^[a-z0-9-]{1,64}$)
description: string (optional)
owner: string (required)
```

**Schema: NamespaceRead**
```
id: UUID
name: string
slug: string
description: string | null
owner: string
created_at: datetime
updated_at: datetime
```

**Schema: NamespaceUpdate**
```
name: string (optional)
description: string (optional)
owner: string (optional)
```

**Request Header**
```
X-Namespace: <slug>   # optional; defaults to "default"
```

### 8.2 Events / Messages

No new events introduced in this change. Future namespace-scoped events are deferred.

### 8.3 Data Model Impact

| ID | Entity | Change |
|---|---|---|
| DM-1 | `namespaces` (new table) | `id UUID PK`, `name VARCHAR(128) UNIQUE NOT NULL`, `slug VARCHAR(64) UNIQUE NOT NULL`, `description TEXT`, `owner VARCHAR(256) NOT NULL`, `created_at TIMESTAMP`, `updated_at TIMESTAMP` |
| DM-2 | `AgentDefinition` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |
| DM-3 | `MCPDefinition` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |
| DM-4 | `FamilyDefinition` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |
| DM-5 | `SkillDefinition` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |
| DM-6 | `WorkflowDefinition` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |
| DM-7 | `Request` | Add `namespace_id UUID NOT NULL FK → namespaces.id`; retain `tenant_id` (deprecated) |
| DM-8 | `Case` | Add `namespace_id UUID NOT NULL FK → namespaces.id`; retain `tenant_id` (deprecated) |
| DM-9 | `OrchestrationPlan` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |
| DM-10 | `Run` | Add `namespace_id UUID NOT NULL FK → namespaces.id` |

### 8.4 External Integrations

None. No external vendor APIs are affected.

### 8.5 Backward Compatibility

- Clients that do **not** send `X-Namespace` continue to work; all operations resolve to the "default" namespace.
- `tenant_id` on `Request` and `Case` is preserved; existing readers/writers are unaffected.
- No existing API response schemas are altered; `namespace_id` is an additive field.

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Namespace resolution dependency adds ≤ 5 ms P99 overhead per request. |
| NFR-2 | Performance | Namespace CRUD endpoints: P50 < 50 ms, P95 < 200 ms under 50 concurrent requests. |
| NFR-3 | Reliability | Migration must be idempotent; re-running on an already-migrated DB must be a no-op. |
| NFR-4 | Data Integrity | After migration, zero rows across all nine tables may have `namespace_id IS NULL`. |
| NFR-5 | Backward Compatibility | Zero existing API integration tests may fail after this change is deployed. |
| NFR-6 | Scalability | `namespace_id` columns must be indexed to support future namespace-scoped queries without full-table scans. |
| NFR-7 | Maintainability | `tenant_id` deprecation must be documented in model docstrings; no new Orkestra-internal code may write `tenant_id`. |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

- Namespace resolution failures (slug-not-found 404s) are logged at `WARNING` level with the requested slug.
- Namespace CRUD operations (create, update, delete) are logged at `INFO` level with `namespace_id` and `owner`.
- Migration execution emits structured log entries at each step (create table, seed, back-fill count per table, alter column).
- A Prometheus counter `orkestra_namespace_resolution_total{result="hit|miss|default"}` is incremented on each resolution.

---

## 11. RISKS & MITIGATIONS

| ID | Risk | Impact | Probability | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| RSK-1 | Migration back-fill locks large tables causing downtime | High | Medium | Run migration during a declared maintenance window; use batched UPDATE with row-count logging; test on staging with production-volume data. | Low |
| RSK-2 | Services or background jobs bypass the FastAPI dependency and perform global (un-namespaced) reads | Medium | High | Audit all service-layer list functions; add integration test asserting every list endpoint filters by namespace when header present. | Medium — deferred filtering is out of scope; full adoption in follow-on. |
| RSK-3 | Slug collision on the "default" seed if migration is run against a DB that already has partial data | Medium | Low | Migration checks for existence before inserting seed row; use fixed UUID constant. | Low |
| RSK-4 | `namespace_id` index missing causes performance regression on high-frequency list queries | Medium | Medium | NFR-6 mandates index creation in migration; verified by EXPLAIN query in integration test. | Low |
| RSK-5 | FK constraint blocks hard-delete of "default" namespace | Low | Low | API-5 returns 409 when referenced entities exist; "default" namespace is protected by convention (document in API contract). | Low |

---

## 12. ASSUMPTIONS

1. PostgreSQL 16 is the target database; migration uses Alembic async with `op.execute` for back-fill.
2. The "default" namespace slug is the string `"default"`; its UUID is a fixed deterministic constant seeded in the migration.
3. All Orkestra services run in the same process context (monolith); no cross-service RPC namespace propagation is required in this change.
4. A maintenance window is acceptable for the migration; zero-downtime migration is not required.
5. `owner` on `Namespace` is a free-form string (e.g., email or username); no user-identity service integration is required.
6. `FamilyDefinition` and its child tables (`SkillFamily`, `AgentSkill`) are treated as registry entities; only `FamilyDefinition` itself receives `namespace_id` (child tables are scoped by their parent FK).

---

## 13. DEPENDENCIES

| Dependency | Type | Notes |
|---|---|---|
| SQLAlchemy async | Internal library | Already in use; no version change required. |
| Alembic | Internal tool | Already configured; migration follows existing patterns. |
| FastAPI dependency injection | Internal framework | Already in use; new dependency added following existing patterns. |
| GH-24 (Namespace epic) | Internal epic | This change is the foundational ticket; all downstream GH-24 tickets depend on it. |

---

## 14. OPEN QUESTIONS

| ID | Question | Owner | Target Date |
|---|---|---|---|
| OQ-1 | Should `RunNode` also receive `namespace_id`, or is it sufficiently scoped through its parent `Run`? Decision needed: consult `@architect`. | mbensass | — |
| OQ-2 | Should the "default" namespace be deletable? Current proposal: hard-delete blocked by FK constraint. Confirm desired behavior. | mbensass | — |
| OQ-3 | Should namespace slugs be validated as DNS-label-safe (RFC 1123) or is the current regex `^[a-z0-9-]{1,64}$` sufficient? | mbensass | — |
| OQ-4 | Is a namespace-scoped event required for namespace creation/deletion for downstream consumers (e.g., audit log service)? Deferred per current scope; confirm. | mbensass | — |

---

## 15. DECISION LOG

| ID | Decision | Rationale | Date |
|---|---|---|---|
| DEC-1 | Namespace is purely logical — no access control | Keeps this change tightly scoped; RBAC is a separate concern in the GH-24 epic roadmap. | 2026-05-01 |
| DEC-2 | `X-Namespace` resolves by slug, not by UUID | Human-readable; consistent with URL path conventions; slugs are immutable after creation. | 2026-05-01 |
| DEC-3 | Missing `X-Namespace` header defaults to "default" (no error) | Backward compatibility — all existing clients continue working unchanged. | 2026-05-01 |
| DEC-4 | `tenant_id` is preserved as deprecated, not removed | Avoids breaking change in this delivery; removal deferred to a subsequent cleanup change. | 2026-05-01 |
| DEC-5 | `FamilyDefinition` child tables (`SkillFamily`, `AgentSkill`) are not directly namespaced | They are scoped implicitly through the parent `FamilyDefinition.namespace_id`; avoids redundant FK proliferation. | 2026-05-01 |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

| Component | Nature of Impact |
|---|---|
| Data model layer | New `Namespace` model; `namespace_id` FK on 9 existing models |
| Database schema | New `namespaces` table; 9 new FK columns; indexes; back-fill migration |
| API layer | New `/api/namespaces` router (5 endpoints) |
| Middleware / dependency | New `X-Namespace` resolution dependency injected into request pipeline |
| Service layer | New `NamespaceService` for CRUD; existing services may receive namespace context |
| Pydantic schemas | New `NamespaceCreate`, `NamespaceRead`, `NamespaceUpdate` schemas |
| Model registry (`__init__.py`) | `Namespace` model exported |

---

## 17. ACCEPTANCE CRITERIA

**AC-F1-1**: Given a `POST /api/namespaces` request with a valid `name`, `slug`, `owner`, When the request is processed, Then a `Namespace` row is persisted with all required fields populated and HTTP 201 is returned with a `NamespaceRead` body.

**AC-F1-2**: Given a `POST /api/namespaces` request with a `slug` that already exists, When the request is processed, Then HTTP 409 is returned and no duplicate row is created.

**AC-F1-3**: Given a `DELETE /api/namespaces/{slug}` request where one or more entities reference that namespace, When the request is processed, Then HTTP 409 is returned and the namespace is not deleted.

**AC-F2-1**: Given the Alembic migration has been applied, When querying each of the nine entity tables, Then every row has a non-null `namespace_id` value equal to the "default" namespace UUID.

**AC-F2-2**: Given a new entity is created via its respective API endpoint with an `X-Namespace: team-alpha` header, When the entity is persisted, Then its `namespace_id` FK references the "team-alpha" namespace and not "default".

**AC-F3-1**: Given an API request with `X-Namespace: team-alpha` where "team-alpha" is a known namespace slug, When the FastAPI dependency resolves, Then the resolved `Namespace` object with slug "team-alpha" is available to the route handler.

**AC-F3-2**: Given an API request with `X-Namespace: nonexistent-slug`, When the FastAPI dependency resolves, Then HTTP 404 is returned with a body containing `{"detail": "Namespace not found"}`.

**AC-F4-1**: Given an API request with no `X-Namespace` header, When the FastAPI dependency resolves, Then the resolved namespace is the "default" namespace and the request proceeds without error.

**AC-F4-2**: Given an existing client that never sends `X-Namespace`, When it calls any existing endpoint (e.g., `GET /api/agents`), Then the response is identical in structure to the pre-change response (no breaking change).

**AC-F5-1**: Given the migration is run against a database with existing rows in all nine tables, When the migration completes, Then all rows have `namespace_id` set to the "default" namespace UUID and the `namespaces` table contains exactly one row with `slug = "default"`.

**AC-F5-2**: Given the migration is run a second time on an already-migrated database, When the migration completes, Then no errors are raised and the database state is unchanged (idempotent).

**AC-F6-1**: Given the migration has been applied, When querying `Request` or `Case` rows, Then `tenant_id` columns are present and retain their original values.

**AC-NFR-1**: Given 50 concurrent requests to any namespaced endpoint with a valid `X-Namespace` header, When measuring response times, Then P95 namespace resolution overhead is ≤ 5 ms above the baseline without namespace resolution.

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

- **Pre-deployment**: declare maintenance window; take database backup.
- **Deployment**: apply Alembic migration (create table → seed → back-fill → alter NOT NULL); deploy updated application.
- **Post-deployment verification**: confirm zero rows with `namespace_id IS NULL` across all nine tables; confirm existing API integration tests pass; confirm `GET /api/namespaces` returns the "default" namespace.
- **Rollback plan**: Alembic downgrade removes `namespace_id` columns and drops `namespaces` table; `tenant_id` is unaffected. Rollback is safe because `namespace_id` is additive.
- **Communication**: internal teams consuming the API are notified of the new optional `X-Namespace` header; no action required for backward compatibility.

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

- **Seed record**: `Namespace(id=<fixed-uuid>, name="Default", slug="default", description="System default namespace", owner="system", ...)`.
- **Fixed UUID**: a deterministic UUID constant must be defined in the migration and reused in application seed fixtures to avoid divergence between environments.
- **Back-fill strategy**: single `UPDATE <table> SET namespace_id = '<default-uuid>' WHERE namespace_id IS NULL` per table; executed within the migration transaction.
- **Volume estimate**: migration must handle up to 100 k rows per table within 5 minutes (NFR-3 / success metric).
- **Verification query**: post-migration assertion `SELECT COUNT(*) FROM <table> WHERE namespace_id IS NULL` must return 0 for all nine tables.

---

## 20. PRIVACY / COMPLIANCE REVIEW

- No personally identifiable information (PII) is introduced by the `Namespace` model.
- The `owner` field stores a principal identifier (e.g., username or email); if email addresses are stored, standard data-handling policies apply.
- No change to data retention or access logging in this iteration.

---

## 21. SECURITY REVIEW HIGHLIGHTS

- **No authorization boundary introduced**: all namespaces are globally visible; this is by design (DEC-1). Future RBAC is deferred.
- **Slug injection**: the `X-Namespace` header value is used only as a database lookup key; it must be validated against the slug regex before any DB query to prevent unexpected behavior.
- **FK constraint as integrity guard**: the `NOT NULL FK` on `namespace_id` prevents orphaned entities from being created; the application layer enforces namespace existence before insert.
- **"default" namespace protection**: the "default" namespace should not be deletable via the API; enforce this via a guard in the delete service function.

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- **Schema complexity**: adds one new table and nine new FK columns; DBA review recommended before migration in production.
- **Index maintenance**: nine new `namespace_id` indexes require periodic `ANALYZE`; no immediate operational impact expected at current scale.
- **Monitoring**: the new `orkestra_namespace_resolution_total` counter should be added to existing dashboards.
- **Future cleanup**: `tenant_id` deprecation removal will require a separate migration and coordination with any external consumers reading those columns.

---

## 23. GLOSSARY

| Term | Definition |
|---|---|
| Namespace | A logical scoping boundary that groups Orkestra entities (agents, MCPs, workflows, etc.) for organizational isolation. No access-control semantics in this iteration. |
| Slug | A URL-safe, human-readable identifier for a namespace (e.g., `team-alpha`). Immutable after creation. |
| Default namespace | The system-seeded namespace with `slug="default"` to which all pre-existing and header-less requests are assigned. |
| `X-Namespace` | HTTP request header carrying the namespace slug for request-scoped context resolution. |
| `namespace_id` | UUID foreign key on entity models referencing the `namespaces` table. |
| `tenant_id` | Legacy string column on `Request` and `Case`; deprecated in favor of `namespace_id`. |
| Back-fill | Migration step that sets `namespace_id` on all existing rows to the "default" namespace UUID. |
| Request-scoped context | FastAPI dependency pattern that resolves a value once per HTTP request and injects it into route handlers. |

---

## 24. APPENDICES

### Appendix A — Nine Models Receiving namespace_id

| Model | Table | Source File (logical reference) |
|---|---|---|
| `AgentDefinition` | `agent_definitions` | registry models |
| `MCPDefinition` | `mcp_definitions` | registry models |
| `FamilyDefinition` | `family_definitions` | family models |
| `SkillDefinition` | `skill_definitions` | skill models |
| `WorkflowDefinition` | `workflow_definitions` | workflow models |
| `Request` | `requests` | request models |
| `Case` | `cases` | case models |
| `OrchestrationPlan` | `orchestration_plans` | plan models |
| `Run` | `runs` | run models |

### Appendix B — Namespace Slug Regex

`^[a-z0-9-]{1,64}$`

Allows lowercase ASCII letters, digits, and hyphens. Maximum 64 characters. No leading/trailing hyphen enforcement in this iteration (see OQ-3).

---

## 25. DOCUMENT HISTORY

| Version | Date | Author | Notes |
|---|---|---|---|
| 0.1 | 2026-05-01 | mbensass | Initial draft — Proposed |

---

## AUTHORING GUIDELINES

- All section IDs (`F-`, `AC-`, `API-`, `DM-`, `NFR-`, `RSK-`, `OQ-`, `DEC-`) must be unique within their category.
- Acceptance Criteria follow Given/When/Then format and reference at least one capability or NFR ID.
- Out-of-scope items are prefixed `[OUT]`.
- NFRs include measurable thresholds.
- Risks include Impact, Probability (H/M/L), Mitigation, and Residual Risk.
- Missing information goes to OPEN QUESTIONS, not to assumptions.

## VALIDATION CHECKLIST

- [x] `change.ref` == `GH-25`
- [x] `owners` ≥ 1 entry
- [x] `status` == "Proposed"
- [x] Section order matches spec_structure
- [x] All ID prefixes are unique within category
- [x] All Acceptance Criteria use Given/When/Then and reference at least one ID
- [x] All NFRs include measurable values
- [x] All Risks include Impact & Probability
- [x] No implementation file paths present
- [x] No code-level tasks present
- [x] Only this spec file will be staged and committed
