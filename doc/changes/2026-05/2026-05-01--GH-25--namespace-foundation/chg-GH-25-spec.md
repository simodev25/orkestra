---
change:
  ref: GH-25
  type: feat
  status: Proposed
  slug: namespace-foundation
  title: "Namespace Foundation — Logical Grouping Primitive for Agent Definitions"
  owners: [mbensass]
  service: core-platform
  labels: [namespace, data-model, api, migration, agents]
  version_impact: minor
  audience: internal
  security_impact: low
  risk_level: medium
  dependencies:
    internal: [registry-service, agent-service]
    external: []
---

# CHANGE SPECIFICATION

> **PURPOSE** — Introduce a `Namespace` model as the canonical logical grouping primitive for `AgentDefinition` entities in Orkestra. Only `AgentDefinition` receives a `namespace_id` foreign key. MCPs, skills, families, workflows, requests, cases, orchestration plans, and runs remain global shared resources with no namespace scoping. A request-scoped FastAPI dependency resolves namespace context from the `X-Namespace` HTTP header (defaulting to "default"). A CRUD API exposes namespace lifecycle management. An Alembic migration seeds the "default" namespace and back-fills all existing agent rows. The orchestrator validates that all `pipeline_agent_ids` reference agents within the same namespace.

---

## 1. SUMMARY

Orkestra currently has no logical isolation boundary for agent definitions. Every agent is globally visible, making it impossible for teams to own and organize their agents independently. MCPs, skills, families, workflows, and all execution entities (requests, cases, plans, runs) are intentionally global shared resources and are not namespaced in this change.

This change introduces a `Namespace` model, attaches `namespace_id` exclusively to `AgentDefinition`, exposes a CRUD API for namespace management, and provides a request-scoped header-based context resolution mechanism. Existing clients with no `X-Namespace` header continue to operate against the "default" namespace without modification.

---

## 2. CONTEXT

### 2.1 Current State Snapshot

- `AgentDefinition` rows are stored globally; no logical grouping or team ownership boundary exists.
- MCPs, skills, families, workflows, requests, cases, orchestration plans, and runs are global shared resources by design.
- The orchestrator's `pipeline_agent_ids` field accepts agent references with no namespace constraint.
- FastAPI route handlers receive no namespace context; agent list/get endpoints return all agents regardless of caller.

### 2.2 Pain Points / Gaps

- **No agent grouping boundary**: agents from different teams share the same global namespace, causing name collisions and operational confusion.
- **No namespace lifecycle management**: no API to create, list, update, or delete namespaces.
- **No propagation mechanism**: even if a namespace column existed on agents, no mechanism would pass namespace context through the HTTP request lifecycle.
- **Cross-namespace orchestration risk**: the orchestrator does not validate that all pipeline agents belong to the same logical group.

---

## 3. PROBLEM STATEMENT

Without a scoping primitive for agent definitions, Orkestra cannot support multi-team deployments where each team must own and manage its own agents in isolation. Any future agent-centric feature (RBAC on agents, namespace-scoped agent quotas, team-level agent dashboards) is blocked until a stable namespace identity exists on `AgentDefinition` and is propagated end-to-end through the HTTP request lifecycle.

---

## 4. GOALS

1. Introduce a `Namespace` entity as the canonical logical grouping primitive for agents.
2. Attach `namespace_id` to `AgentDefinition` **only** — MCPs, skills, families, workflows, requests, cases, plans, and runs remain global.
3. Provide a request-scoped namespace context resolved from the `X-Namespace` header.
4. Expose a CRUD API for namespace lifecycle management.
5. Migrate all existing agent rows to the "default" namespace with zero data loss.
6. Enforce same-namespace constraint in the orchestrator's pipeline agent validation.

### 4.1 Success Metrics / KPIs

| Metric | Target |
|---|---|
| `AgentDefinition` rows without `namespace_id` after migration | 0 |
| Existing API clients broken by this change | 0 |
| Requests missing `X-Namespace` header resolved to "default" | 100 % |
| Migration duration (on representative dataset ≤ 100 k agent rows) | < 5 min |
| Namespace CRUD endpoints P95 response time | < 200 ms |
| Orchestrator rejections for cross-namespace `pipeline_agent_ids` | HTTP 422 with clear message |

### 4.2 Non-Goals

- [OUT] `namespace_id` on `MCPDefinition`, `FamilyDefinition`, `SkillDefinition`, `WorkflowDefinition`.
- [OUT] `namespace_id` on `Request`, `Case`, `OrchestrationPlan`, `Run`.
- [OUT] Access control or permission enforcement on namespaces.
- [OUT] Namespace-scoped visibility policies (namespaces remain globally readable).
- [OUT] `tenant_id` removal (if present on any model).
- [OUT] Namespace quota or rate-limit enforcement.
- [OUT] UI/frontend changes for namespace selection.
- [OUT] Namespace-aware audit log filtering.

---

## 5. FUNCTIONAL CAPABILITIES

| ID | Capability | Rationale |
|---|---|---|
| F-1 | Namespace entity lifecycle (create, read, update, delete) | Required to manage the set of available namespaces as a first-class resource. |
| F-2 | `namespace_id` FK on `AgentDefinition` only | Provides a stable, queryable grouping column for agents without imposing scoping on global shared resources. |
| F-3 | Request-scoped namespace context resolution | Enables agent service functions to receive namespace context without caller-side plumbing. |
| F-4 | `X-Namespace` header propagation with "default" fallback | Ensures backward compatibility for existing clients sending no header. |
| F-5 | Agent list and get endpoints filtered by namespace | Ensures that when a namespace is provided, only agents in that namespace are returned. |
| F-6 | Data migration: seed "default", back-fill agent rows, enforce NOT NULL | Guarantees referential integrity on all existing `AgentDefinition` rows after deployment. |
| F-7 | Orchestrator same-namespace validation for `pipeline_agent_ids` | Prevents orchestration plans from mixing agents across different logical groups. |

### 5.1 Capability Details

**F-1 — Namespace Entity**

The `Namespace` model carries: `id` (UUID PK), `name` (human-readable, unique), `slug` (URL-safe identifier, unique, immutable after creation), `description` (optional text), `created_at`, `updated_at`. Hard-delete is permitted only when no agent definitions reference the namespace. The "default" namespace is protected from deletion.

**F-2 — namespace_id FK on AgentDefinition only**

`AgentDefinition` receives `namespace_id UUID NOT NULL REFERENCES namespaces(id)`. No other model receives this column. MCPs, skills, families, workflows, and all execution entities remain global and unmodified by this change.

**F-3 — Request-Scoped Context**

A FastAPI dependency resolves namespace from the incoming `X-Namespace` header. If the header is absent or empty, the dependency resolves to the "default" namespace. The dependency validates that the resolved namespace exists; if not found, it returns HTTP 404. The resolved `Namespace` object is injected into agent route handlers.

**F-4 — Header Propagation**

The `X-Namespace` header value is treated as a namespace `slug`. Resolution logic: exact slug match → resolved; header absent → "default" slug used; slug not found → HTTP 404 (unless header absent, in which case "default" is guaranteed to exist post-migration).

**F-5 — Agent Filtering by Namespace**

Agent list and get endpoints (`GET /api/agents`, `GET /api/agents/{id}`) apply a `WHERE namespace_id = <resolved>` filter. Clients without `X-Namespace` header see only "default" namespace agents, maintaining backward-compatible behavior.

**F-6 — Migration**

Alembic migration steps (single migration file):
1. Create `namespaces` table.
2. Insert the "default" namespace row (fixed deterministic UUID).
3. Add `namespace_id` as nullable FK to `agent_definitions`.
4. `UPDATE agent_definitions SET namespace_id = '<default-uuid>'`.
5. Alter `namespace_id` to `NOT NULL`.

**F-7 — Orchestrator Same-Namespace Validation**

When an orchestration plan is created or validated with `pipeline_agent_ids`, the orchestrator service verifies that all referenced `AgentDefinition` rows share the same `namespace_id`. If any agent belongs to a different namespace, the request is rejected with HTTP 422 and a descriptive error.

---

## 6. USER & SYSTEM FLOWS

### Flow A — Client with X-Namespace header (agent list)

```
Client → GET /api/agents  [X-Namespace: team-alpha]
  → Dependency resolves slug "team-alpha" → Namespace{id: <uuid>}
  → Agent service queries: SELECT * FROM agent_definitions WHERE namespace_id = <uuid>
  → Response 200 with agents scoped to "team-alpha"
```

### Flow B — Legacy client without X-Namespace header

```
Client → GET /api/agents  [no X-Namespace]
  → Dependency resolves to "default" namespace
  → Agent service queries: SELECT * FROM agent_definitions WHERE namespace_id = <default-uuid>
  → Response 200  (behavior identical to pre-change for legacy clients)
```

### Flow C — Namespace CRUD

```
Admin → POST /api/namespaces  {name, slug, description}
  → Namespace created, 201 returned
Admin → GET  /api/namespaces        → list all namespaces
Admin → GET  /api/namespaces/{slug} → single namespace
Admin → PUT  /api/namespaces/{slug} → update name/description
Admin → DELETE /api/namespaces/{slug} → hard-delete if no agents reference it
```

### Flow D — Invalid namespace slug

```
Client → GET /api/agents  [X-Namespace: nonexistent]
  → Dependency → slug lookup fails → HTTP 404 {"detail": "Namespace not found"}
```

### Flow E — Cross-namespace orchestration rejection

```
User → POST /api/orchestrations  {pipeline_agent_ids: [agent-A (ns: team-alpha), agent-B (ns: team-beta)]}
  → Orchestrator validates namespace_id consistency across all agents
  → All agents NOT in same namespace → HTTP 422 {"detail": "All pipeline agents must belong to the same namespace"}
```

---

## 7. SCOPE & BOUNDARIES

### 7.1 In Scope

- `Namespace` SQLAlchemy async model.
- `namespace_id` FK column on `AgentDefinition` only.
- Alembic migration (create `namespaces` table, seed "default", back-fill `agent_definitions`, enforce NOT NULL).
- FastAPI dependency for request-scoped namespace context resolution.
- REST CRUD endpoints: `GET/POST /api/namespaces`, `GET/PUT/DELETE /api/namespaces/{slug}`.
- Pydantic schemas for namespace request/response.
- Service-layer functions for namespace CRUD.
- Agent list and get endpoint namespace filter.
- Backward-compatible default resolution for missing `X-Namespace` header.
- Orchestrator same-namespace validation for `pipeline_agent_ids`.

### 7.2 Out of Scope

- [OUT] `namespace_id` on `MCPDefinition`, `FamilyDefinition`, `SkillDefinition`, `WorkflowDefinition`.
- [OUT] `namespace_id` on `Request`, `Case`, `OrchestrationPlan`, `Run`.
- [OUT] Access control / RBAC on namespaces.
- [OUT] Namespace-scoped filtering on any endpoint other than agent list/get.
- [OUT] Frontend/UI changes.
- [OUT] Namespace quota enforcement.
- [OUT] Namespace-aware audit logging.

### 7.3 Deferred / Maybe-Later

- Namespace scoping for MCPs, skills, families, workflows (separate epic tickets in GH-24).
- Soft-delete / archival of namespaces.
- Namespace ownership and RBAC.
- Namespace-scoped events for downstream consumers.

---

## 8. INTERFACES & INTEGRATION CONTRACTS

### 8.1 REST / HTTP Endpoints

| ID | Method | Path | Request Body | Response | Notes |
|---|---|---|---|---|---|
| API-1 | POST | `/api/namespaces` | `NamespaceCreate` | `201 NamespaceRead` | Slug must be unique |
| API-2 | GET | `/api/namespaces` | — | `200 List[NamespaceRead]` | Pagination via `limit`/`offset` |
| API-3 | GET | `/api/namespaces/{slug}` | — | `200 NamespaceRead` \| `404` | Lookup by slug |
| API-4 | PUT | `/api/namespaces/{slug}` | `NamespaceUpdate` | `200 NamespaceRead` \| `404` | Slug immutable |
| API-5 | DELETE | `/api/namespaces/{slug}` | — | `204` \| `404` \| `409` | 409 if agent definitions reference this namespace; "default" is additionally protected |
| API-6 | GET | `/api/agents` | — | `200 List[AgentRead]` | Filtered by resolved namespace from `X-Namespace` header |
| API-7 | GET | `/api/agents/{id}` | — | `200 AgentRead` \| `404` | 404 if agent exists but is in a different namespace |

**Schema: NamespaceCreate**
```
name: string (required, max 128)
slug: string (required, pattern: ^[a-z0-9-]{1,64}$)
description: string (optional)
```

**Schema: NamespaceRead**
```
id: UUID
name: string
slug: string
description: string | null
created_at: datetime
updated_at: datetime
```

**Schema: NamespaceUpdate**
```
name: string (optional)
description: string (optional)
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
| DM-1 | `namespaces` (new table) | `id UUID PK`, `name VARCHAR(128) UNIQUE NOT NULL`, `slug VARCHAR(64) UNIQUE NOT NULL`, `description TEXT`, `created_at TIMESTAMP`, `updated_at TIMESTAMP` |
| DM-2 | `AgentDefinition` | Add `namespace_id UUID NOT NULL FK → namespaces.id`; index on `namespace_id` |
| DM-3 | `MCPDefinition` | **No change** — global shared resource |
| DM-4 | `FamilyDefinition` | **No change** — global shared resource |
| DM-5 | `SkillDefinition` | **No change** — global shared resource |
| DM-6 | `WorkflowDefinition` | **No change** — global shared resource |
| DM-7 | `Request` | **No change** — global execution entity |
| DM-8 | `Case` | **No change** — global execution entity |
| DM-9 | `OrchestrationPlan` | **No change** — global execution entity |
| DM-10 | `Run` | **No change** — global execution entity |

### 8.4 External Integrations

None. No external vendor APIs are affected.

### 8.5 Backward Compatibility

- Clients that do **not** send `X-Namespace` continue to work; all agent operations resolve to the "default" namespace.
- Agent response schemas are unchanged; `namespace_id` is an additive field (not required in responses unless explicitly requested).
- No existing API response schemas for non-agent entities are altered.
- MCPs, skills, families, workflows, requests, cases, plans, and runs are completely unaffected.

---

## 9. NON-FUNCTIONAL REQUIREMENTS (NFRs)

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Namespace resolution dependency adds ≤ 5 ms P99 overhead per request. |
| NFR-2 | Performance | Namespace CRUD endpoints: P50 < 50 ms, P95 < 200 ms under 50 concurrent requests. |
| NFR-3 | Reliability | Migration must be idempotent; re-running on an already-migrated DB must be a no-op. |
| NFR-4 | Data Integrity | After migration, zero `AgentDefinition` rows may have `namespace_id IS NULL`. |
| NFR-5 | Backward Compatibility | Zero existing API integration tests may fail after this change is deployed. |
| NFR-6 | Scalability | `namespace_id` on `agent_definitions` must be indexed to support namespace-scoped queries without full-table scans. |

---

## 10. TELEMETRY & OBSERVABILITY REQUIREMENTS

- Namespace resolution failures (slug-not-found 404s) are logged at `WARNING` level with the requested slug.
- Namespace CRUD operations (create, update, delete) are logged at `INFO` level with `namespace_id`.
- Migration execution emits structured log entries at each step (create table, seed, back-fill count, alter column).
- Orchestrator same-namespace validation rejections are logged at `WARNING` level with the conflicting agent IDs and their respective namespace slugs.

---

## 11. RISKS & MITIGATIONS

| ID | Risk | Impact | Probability | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| RSK-1 | Agent service list/get functions miss the namespace filter, exposing cross-namespace agents | Medium | Medium | Audit all agent service query functions; integration test asserts list endpoint returns only namespace-scoped agents when `X-Namespace` header is set. | Low |
| RSK-2 | Migration back-fill locks `agent_definitions` table causing downtime | Medium | Low | Run migration during a declared maintenance window; use batched UPDATE with row-count logging; test on staging with production-volume data. | Low |
| RSK-3 | Slug collision on the "default" seed if migration is run against a DB with partial data | Medium | Low | Migration checks for existence before inserting seed row; use fixed UUID constant. | Low |
| RSK-4 | `namespace_id` index missing causes performance regression on agent list queries | Medium | Medium | NFR-6 mandates index creation in migration; verified by EXPLAIN query in integration test. | Low |
| RSK-5 | Orchestrator validation logic incomplete — only checks subset of `pipeline_agent_ids` | Medium | Low | Unit test covering mixed-namespace agent list; test verifies 422 returned in all cross-namespace cases. | Low |

---

## 12. ASSUMPTIONS

1. PostgreSQL 16 is the target database; migration uses Alembic async with `op.execute` for back-fill.
2. The "default" namespace slug is the string `"default"`; its UUID is a fixed deterministic constant seeded in the migration.
3. All Orkestra services run in the same process context (monolith); no cross-service RPC namespace propagation is required in this change.
4. A maintenance window is acceptable for the migration; zero-downtime migration is not required.
5. MCPs, skills, families, workflows, requests, cases, plans, and runs are intentionally global and will remain so unless explicitly scoped in a future GH-24 epic ticket.

---

## 13. DEPENDENCIES

| Dependency | Type | Notes |
|---|---|---|
| SQLAlchemy async | Internal library | Already in use; no version change required. |
| Alembic | Internal tool | Already configured; migration follows existing patterns. |
| FastAPI dependency injection | Internal framework | Already in use; new dependency added following existing patterns. |
| GH-24 (Namespace epic) | Internal epic | This change is the foundational ticket; downstream GH-24 tickets depend on it. |

---

## 14. OPEN QUESTIONS

| ID | Question | Owner | Target Date |
|---|---|---|---|
| OQ-1 | Should `GET /api/agents/{id}` return 404 or 403 when the agent exists but is in a different namespace than the resolved `X-Namespace`? Decision needed: consult `@architect`. | mbensass | — |
| OQ-2 | Should the "default" namespace be deletable at all, or should the API hard-reject DELETE on it? Current proposal: API-5 blocks delete if any agents reference it; "default" always has agents post-migration. Confirm desired behavior. | mbensass | — |
| OQ-3 | Should namespace slugs be validated as DNS-label-safe (RFC 1123) or is the current regex `^[a-z0-9-]{1,64}$` sufficient? | mbensass | — |
| OQ-4 | Should the orchestrator same-namespace validation (F-7) also apply to agent references outside `pipeline_agent_ids` (e.g., step-level agent assignments)? | mbensass | — |

---

## 15. DECISION LOG

| ID | Decision | Rationale | Date |
|---|---|---|---|
| DEC-1 | `namespace_id` is added to `AgentDefinition` only — not to MCPs, skills, families, workflows, or execution entities | Keeps the change tightly scoped to agent grouping; global shared resources (MCPs, skills, families, workflows) must remain accessible from all namespaces; execution entities (requests, cases, plans, runs) are global by design in this iteration. | 2026-05-01 |
| DEC-2 | Namespace is purely logical — no access control | Keeps this change tightly scoped; RBAC is a separate concern in the GH-24 epic roadmap. | 2026-05-01 |
| DEC-3 | `X-Namespace` resolves by slug, not by UUID | Human-readable; consistent with URL path conventions; slugs are immutable after creation. | 2026-05-01 |
| DEC-4 | Missing `X-Namespace` header defaults to "default" (no error) | Backward compatibility — all existing clients continue working unchanged. | 2026-05-01 |
| DEC-5 | Orchestrator validates same-namespace constraint for `pipeline_agent_ids` | Prevents logical inconsistency where an orchestration plan mixes agents from different teams' namespaces. | 2026-05-01 |

---

## 16. AFFECTED COMPONENTS (HIGH-LEVEL)

| Component | Nature of Impact |
|---|---|
| Data model layer | New `Namespace` model; `namespace_id` FK on `AgentDefinition` only |
| Database schema | New `namespaces` table; one new FK column on `agent_definitions`; index; back-fill migration |
| API layer | New `/api/namespaces` router (5 endpoints); updated agent endpoints (namespace filter) |
| Middleware / dependency | New `X-Namespace` resolution dependency injected into agent and namespace request pipeline |
| Service layer | New namespace CRUD service; agent service updated to accept namespace filter |
| Pydantic schemas | New `NamespaceCreate`, `NamespaceRead`, `NamespaceUpdate` schemas; `AgentRead` gains `namespace_id` field |
| Orchestration service | `pipeline_agent_ids` validation extended with same-namespace check |

---

## 17. ACCEPTANCE CRITERIA

**AC-F1-1**: Given a `POST /api/namespaces` request with a valid `name` and `slug`, When the request is processed, Then a `Namespace` row is persisted with all required fields populated and HTTP 201 is returned with a `NamespaceRead` body.

**AC-F1-2**: Given a `POST /api/namespaces` request with a `slug` that already exists, When the request is processed, Then HTTP 409 is returned and no duplicate row is created.

**AC-F1-3**: Given a `DELETE /api/namespaces/{slug}` request where one or more `AgentDefinition` rows reference that namespace, When the request is processed, Then HTTP 409 is returned and the namespace is not deleted.

**AC-F2-1**: Given the Alembic migration has been applied, When querying `agent_definitions`, Then every row has a non-null `namespace_id` value equal to the "default" namespace UUID.

**AC-F2-2**: Given a new agent is created via `POST /api/agents` with an `X-Namespace: team-alpha` header, When the agent is persisted, Then its `namespace_id` FK references the "team-alpha" namespace and not "default".

**AC-F2-3**: Given the Alembic migration has been applied, When querying `mcp_definitions`, `family_definitions`, `skill_definitions`, `workflow_definitions`, `requests`, `cases`, `orchestration_plans`, and `runs`, Then none of these tables have a `namespace_id` column.

**AC-F3-1**: Given an API request with `X-Namespace: team-alpha` where "team-alpha" is a known namespace slug, When the FastAPI dependency resolves, Then the resolved `Namespace` object with slug "team-alpha" is available to the agent route handler.

**AC-F3-2**: Given an API request with `X-Namespace: nonexistent-slug`, When the FastAPI dependency resolves, Then HTTP 404 is returned with a body containing `{"detail": "Namespace not found"}`.

**AC-F4-1**: Given an API request with no `X-Namespace` header, When the FastAPI dependency resolves, Then the resolved namespace is the "default" namespace and the request proceeds without error.

**AC-F4-2**: Given an existing client that never sends `X-Namespace`, When it calls `GET /api/agents`, Then the response contains only agents in the "default" namespace and the response structure is unchanged from the pre-change contract.

**AC-F5-1**: Given the agent list endpoint `GET /api/agents` is called with `X-Namespace: team-alpha`, When the response is returned, Then only agents whose `namespace_id` matches the "team-alpha" namespace are included.

**AC-F5-2**: Given an agent in namespace "team-alpha" and `GET /api/agents/{id}` is called with `X-Namespace: team-beta`, When the request is processed, Then HTTP 404 is returned (agent not visible in the requested namespace).

**AC-F6-1**: Given the migration is run against a database with existing `AgentDefinition` rows, When the migration completes, Then all agent rows have `namespace_id` set to the "default" namespace UUID and the `namespaces` table contains the "default" row.

**AC-F6-2**: Given the migration is run a second time on an already-migrated database, When the migration completes, Then no errors are raised and the database state is unchanged (idempotent).

**AC-F7-1**: Given an orchestration plan creation request with `pipeline_agent_ids` referencing agents from two different namespaces, When the orchestrator validates the request, Then HTTP 422 is returned with a message indicating all pipeline agents must belong to the same namespace.

**AC-F7-2**: Given an orchestration plan creation request with `pipeline_agent_ids` referencing agents all in the same namespace, When the orchestrator validates the request, Then the same-namespace validation passes and the plan is created successfully.

**AC-NFR-1**: Given 50 concurrent requests to any agent endpoint with a valid `X-Namespace` header, When measuring response times, Then P95 namespace resolution overhead is ≤ 5 ms above the baseline without namespace resolution.

---

## 18. ROLLOUT & CHANGE MANAGEMENT (HIGH-LEVEL)

- **Pre-deployment**: declare maintenance window; take database backup.
- **Deployment**: apply Alembic migration (create `namespaces` table → seed "default" → back-fill `agent_definitions` → alter NOT NULL); deploy updated application.
- **Post-deployment verification**: confirm zero `AgentDefinition` rows with `namespace_id IS NULL`; confirm existing API integration tests pass; confirm `GET /api/namespaces` returns the "default" namespace; confirm `GET /api/agents` (no header) returns agents scoped to "default".
- **Rollback plan**: Alembic downgrade removes `namespace_id` column from `agent_definitions` and drops `namespaces` table. All other models are unaffected. Rollback is safe because the change is additive to one table only.
- **Communication**: internal teams consuming the agents API are notified of the new optional `X-Namespace` header; no action required for backward compatibility.

---

## 19. DATA MIGRATION / SEEDING (IF APPLICABLE)

- **Seed record**: `Namespace(id=<fixed-uuid>, name="Default", slug="default", description="System default namespace", ...)`.
- **Fixed UUID**: a deterministic UUID constant must be defined in the migration and reused in application seed fixtures to avoid divergence between environments.
- **Back-fill strategy**: single `UPDATE agent_definitions SET namespace_id = '<default-uuid>' WHERE namespace_id IS NULL`; executed within the migration transaction.
- **Volume estimate**: migration must handle up to 100 k `AgentDefinition` rows within 5 minutes.
- **Verification query**: post-migration assertion `SELECT COUNT(*) FROM agent_definitions WHERE namespace_id IS NULL` must return 0.

---

## 20. PRIVACY / COMPLIANCE REVIEW

- No personally identifiable information (PII) is introduced by the `Namespace` model.
- No change to data retention or access logging in this iteration.

---

## 21. SECURITY REVIEW HIGHLIGHTS

- **No authorization boundary introduced**: all namespaces are globally visible; this is by design (DEC-2). Future RBAC is deferred.
- **Slug injection**: the `X-Namespace` header value is used only as a database lookup key; it must be validated against the slug regex before any DB query.
- **FK constraint as integrity guard**: the `NOT NULL FK` on `namespace_id` prevents orphaned agent definitions from being created; the application layer enforces namespace existence before insert.
- **"default" namespace protection**: the "default" namespace must not be deletable via the API; enforce this via a guard in the delete service function (additionally protected by FK constraint post-migration).

---

## 22. MAINTENANCE & OPERATIONS IMPACT

- **Schema complexity**: adds one new table and one new FK column on `agent_definitions`; DBA review recommended before migration in production.
- **Index maintenance**: the new `namespace_id` index on `agent_definitions` requires periodic `ANALYZE`; no immediate operational impact at current scale.
- **Future extension**: adding `namespace_id` to other models in future GH-24 tickets will follow the same pattern established here.

---

## 23. GLOSSARY

| Term | Definition |
|---|---|
| Namespace | A logical grouping boundary for `AgentDefinition` entities. No access-control semantics in this iteration. |
| Slug | A URL-safe, human-readable identifier for a namespace (e.g., `team-alpha`). Immutable after creation. |
| Default namespace | The system-seeded namespace with `slug="default"` to which all pre-existing agents and header-less requests are assigned. |
| `X-Namespace` | HTTP request header carrying the namespace slug for request-scoped context resolution. |
| `namespace_id` | UUID foreign key on `AgentDefinition` referencing the `namespaces` table. |
| Global shared resource | An entity (MCP, skill, family, workflow, request, case, plan, run) accessible from all namespaces with no namespace scoping in this change. |
| Request-scoped context | FastAPI dependency pattern that resolves a value once per HTTP request and injects it into route handlers. |
| Same-namespace validation | Orchestrator check that all `pipeline_agent_ids` reference agents belonging to the same namespace. |

---

## 24. APPENDICES

### Appendix A — Scope Boundary Summary

| Model | Gets namespace_id? | Rationale |
|---|---|---|
| `AgentDefinition` | **YES** | Logical grouping primitive — agents must be team-owned. |
| `MCPDefinition` | No | Global shared resource — accessible from all namespaces. |
| `FamilyDefinition` | No | Global shared resource. |
| `SkillDefinition` | No | Global shared resource. |
| `WorkflowDefinition` | No | Global shared resource. |
| `Request` | No | Global execution entity. |
| `Case` | No | Global execution entity. |
| `OrchestrationPlan` | No | Global execution entity. |
| `Run` | No | Global execution entity. |

### Appendix B — Namespace Slug Regex

`^[a-z0-9-]{1,64}$`

Allows lowercase ASCII letters, digits, and hyphens. Maximum 64 characters. No leading/trailing hyphen enforcement in this iteration (see OQ-3).

---

## 25. DOCUMENT HISTORY

| Version | Date | Author | Notes |
|---|---|---|---|
| 0.1 | 2026-05-01 | mbensass | Initial draft — Proposed |
| 0.2 | 2026-05-01 | mbensass | Revised scope: namespace_id on AgentDefinition ONLY; all other models remain global; added F-7 orchestrator same-namespace validation; added AC-F2-3, AC-F5-1, AC-F5-2, AC-F7-1, AC-F7-2; removed owner field from Namespace model per planning context |

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
