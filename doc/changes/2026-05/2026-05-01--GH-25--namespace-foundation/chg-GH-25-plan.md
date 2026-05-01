---
id: chg-GH-25-namespace-foundation
status: Proposed
created: 2026-05-01T15:13:16Z
last_updated: 2026-05-01T15:13:16Z
owners: [mbensass]
service: core-platform
labels: [namespace, data-model, api, migration, agents]
links:
  change_spec: doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-spec.md
summary: >-
  Introduce a `Namespace` model as the canonical logical grouping primitive for
  `AgentDefinition` only. Add request-scoped namespace resolution via the
  `X-Namespace` header (defaulting to "default"), provide namespace CRUD APIs,
  migrate existing agents to the seeded "default" namespace, and enforce
  same-namespace validation for orchestrator `pipeline_agent_ids`.
version_impact: minor
---

## Context and Goals

This change introduces namespace as a *logical grouping primitive* for agent definitions, without altering MCPs, skills, families, workflows, or execution entities (requests/cases/plans/runs), which remain global shared resources.

**Goals (from spec):**

- Introduce a `Namespace` entity and its lifecycle API.
- Add `namespace_id` **only** to `AgentDefinition`.
- Resolve namespace context from `X-Namespace` header (slug) with a "default" fallback.
- Filter agent list/get by resolved namespace.
- Migrate existing agent rows to "default" and enforce `namespace_id NOT NULL`.
- Enforce same-namespace constraint for orchestrator `pipeline_agent_ids`.

**Open questions (from spec):**

- OQ-1: Should `GET /api/agents/{id}` return 404 or 403 when the agent exists but is in a different namespace? Decision needed: consult `@architect`.
- OQ-2: Should the "default" namespace be deletable at all, or should the API hard-reject DELETE on it? Confirm desired behavior.
- OQ-3: Should namespace slugs be validated as RFC 1123/DNS-label-safe vs current regex `^[a-z0-9-]{1,64}$`?
- OQ-4: Should same-namespace validation apply beyond `pipeline_agent_ids` (e.g., step-level agent assignments), or only to `pipeline_agent_ids` for this ticket?

## Scope

### In Scope

- New `Namespace` SQLAlchemy model and `namespaces` table.
- Add `namespace_id` FK to `AgentDefinition` only (indexed; `NOT NULL` after migration).
- Alembic migration: create table, seed "default" namespace (fixed UUID), back-fill all agents, enforce NOT NULL.
- FastAPI request-scoped namespace resolution dependency based on `X-Namespace` header slug with "default" fallback.
- Namespace CRUD API:
  - `POST /api/namespaces`
  - `GET /api/namespaces` (offset/limit)
  - `GET /api/namespaces/{slug}`
  - `PUT /api/namespaces/{slug}` (slug immutable)
  - `DELETE /api/namespaces/{slug}` (409 if referenced; additionally protect "default")
- Update agent list/get behavior to apply namespace filtering via the resolved namespace.
- Orchestrator validation: reject cross-namespace `pipeline_agent_ids` with HTTP 422.
- Observability per spec: log slug-not-found resolution failures (WARN), CRUD actions (INFO), orchestrator rejections (WARN).

### Out of Scope

- Adding `namespace_id` to MCPs, skills, families, workflows.
- Adding `namespace_id` to requests, cases, orchestration plans, runs.
- RBAC / permission enforcement for namespaces.
- Namespace-aware filtering for endpoints other than agent list/get.
- Frontend/UI changes.

### Constraints

- `namespace_id` is introduced on `AgentDefinition` **only**.
- `X-Namespace` header is treated as a namespace **slug**; missing/empty header resolves to slug `default`.
- The "default" namespace must exist post-migration and must not be deletable via API.
- Migration must be idempotent (safe to re-run).
- Performance: namespace resolution overhead should remain within spec thresholds.

### Risks

- Missing namespace filter in an agent query path could expose cross-namespace agent visibility.
- Migration back-fill could lock the agents table for longer than expected.
- Index omission could regress agent list performance.
- Orchestrator validation might miss some agent reference paths (if more exist beyond `pipeline_agent_ids`).

### Success Metrics

- 0 `AgentDefinition` rows with `namespace_id IS NULL` after migration.
- Legacy clients (no `X-Namespace`) continue working and see only "default" agents.
- Namespace CRUD endpoints behave per acceptance criteria (including 409 on slug conflict / referenced delete).
- Cross-namespace `pipeline_agent_ids` rejected with HTTP 422 and clear error.

## Phases

### Phase 1: Data model + migration scaffolding

**Goal**: Establish the `Namespace` persistence layer and make `AgentDefinition.namespace_id` a required FK with a safe back-fill.

**Tasks**:

- [ ] Add SQLAlchemy async model `Namespace` (UUID PK; `name` unique; `slug` unique, immutable; optional `description`; timestamps).
- [ ] Update `AgentDefinition` model to include `namespace_id` FK (and relationship if used) and ensure `namespace_id` is required at the ORM layer after migration.
- [ ] Create a single Alembic migration implementing spec steps:
  - create `namespaces` table
  - seed "default" namespace (fixed deterministic UUID)
  - add nullable `namespace_id` FK to `agent_definitions`
  - back-fill existing rows to default UUID
  - enforce `NOT NULL`
  - add index on `agent_definitions.namespace_id`
- [ ] Ensure migration is idempotent (guards around seed insert; safe re-run behavior).

**Acceptance Criteria**:

- Must: Migration results in 0 agents with `namespace_id IS NULL`.
- Must: `namespaces` contains the seeded "default" namespace.
- Must: No `namespace_id` column appears on any non-agent model/table listed as out-of-scope.
- Should: Migration is safe to apply twice without errors.

**Files and modules**:

- `app/models/` (new Namespace model; update AgentDefinition)
- `alembic/versions/` (new migration)

**Tests**:

- Migration-focused test/verification (apply upgrade; assert default seeded; assert agent back-fill; assert idempotency).

**Completion signal**: Commit: `feat(namespace): add namespaces table and agent namespace_id migration`

### Phase 2: Namespace resolution dependency and CRUD API

**Goal**: Provide request-scoped namespace context resolution and implement namespace lifecycle endpoints.

**Tasks**:

- [ ] Implement request-scoped FastAPI dependency to resolve namespace by slug from `X-Namespace` header:
  - absent/empty → resolve to slug `default`
  - invalid format (fails slug regex) → return validation error (HTTP 422)
  - slug not found → HTTP 404 `{"detail": "Namespace not found"}`
- [ ] Add Pydantic schemas: `NamespaceCreate`, `NamespaceRead`, `NamespaceUpdate`.
- [ ] Add service-layer CRUD functions for namespaces (create/list/get/update/delete) including:
  - unique slug conflict → HTTP 409
  - delete guard: block deleting "default"; block deleting any referenced by `AgentDefinition` (HTTP 409)
- [ ] Add routes under `app/api/routes/` for namespace CRUD per API table in spec.
- [ ] Add structured logging per spec for CRUD operations and resolution failures.

**Acceptance Criteria**:

- Must: CRUD endpoints match request/response behavior defined in spec (including 409 conflict and delete protections).
- Must: Unknown slug in `X-Namespace` yields HTTP 404 with exact detail.
- Must: Missing header resolves to "default" and proceeds.

**Files and modules**:

- `app/api/routes/` (new namespaces router)
- `app/services/` (namespace service module)
- `app/api/dependencies/` (or existing dependency module for request-scoped context)
- `app/schemas/` (namespace schemas; if project uses different location, follow existing conventions)

**Tests**:

- API tests for namespace CRUD (happy paths + conflict + delete guards).
- Dependency tests for header absent/empty, invalid slug format, slug-not-found.

**Completion signal**: Commit: `feat(namespace): add namespace CRUD and X-Namespace resolution dependency`

### Phase 3: Agent scoping + orchestrator validation

**Goal**: Ensure agent list/get are namespace-scoped and orchestrations cannot mix namespaces in `pipeline_agent_ids`.

**Tasks**:

- [ ] Update agent list/get endpoints to require resolved namespace dependency and filter queries by `namespace_id`.
- [ ] Ensure legacy behavior: calls without `X-Namespace` see only agents in "default".
- [ ] Implement orchestrator validation for `pipeline_agent_ids`:
  - fetch referenced `AgentDefinition` rows
  - assert all have same `namespace_id`
  - on mismatch → HTTP 422 with message per spec
- [ ] Add logging for orchestrator rejections including agent IDs and their namespace slugs.

**Acceptance Criteria**:

- Must: `GET /api/agents` with `X-Namespace: team-alpha` returns only team-alpha agents.
- Must: `GET /api/agents/{id}` with mismatched namespace returns the decided behavior (currently spec expects 404; confirm OQ-1).
- Must: Mixed-namespace `pipeline_agent_ids` is rejected with HTTP 422 and clear message.

**Files and modules**:

- `app/api/routes/` (agents routes adjustments)
- `app/services/` (agent query functions updated to accept namespace filter)
- Orchestrator service module(s) handling orchestration plan creation/validation

**Tests**:

- Integration tests for agent list/get namespace filtering.
- Unit/integration tests for orchestrator same-namespace validation (pass + fail cases).

**Completion signal**: Commit: `feat(namespace): scope agents by namespace and validate orchestrator pipeline_agent_ids`

### Phase 4: Documentation & Spec Synchronization

**Goal**: Ensure change artifacts and system documentation remain consistent with the implemented behavior.

**Tasks**:

- [ ] Reconcile any implementation-discovered details back into the change spec if needed (only if spec changes are required).
- [ ] Run `/sync-docs GH-25` after implementation to update `doc/spec/**` if applicable.
- [ ] Ensure API docs (if generated) reflect `X-Namespace` header behavior and namespace endpoints.

**Acceptance Criteria**:

- Must: Spec and implementation agree on: slug regex, default fallback, status codes (404/409/422), and scope boundaries.

**Files and modules**:

- `doc/spec/**` (via `/sync-docs` step)

**Tests**:

- N/A (documentation verification via review checklist).

**Completion signal**: Commit: `docs: sync specs for GH-25`

### Phase 5: Code Review (Analysis)

**Goal**: Validate implementation against spec acceptance criteria and repo conventions.

**Tasks**:

- [ ] Run an internal review against ACs (focus: scoping boundaries; migration safety; error codes; logging).
- [ ] Verify no unintended namespace changes were introduced on MCP/skill/family/workflow/execution models.

**Acceptance Criteria**:

- Must: All ACs in spec are demonstrably satisfied or explicitly deferred with documented rationale.

**Files and modules**:

- N/A

**Tests**:

- Execute the test suite relevant to API + DB migration paths.

**Completion signal**: Review notes captured; ready for fixups (if any)

### Phase 6: Post-Code Review Fixes (conditional)

**Goal**: Address any issues found in Phase 5.

**Tasks**:

- [ ] Apply fixes and add/adjust tests to prevent regressions.

**Acceptance Criteria**:

- Must: All Phase 5 findings are resolved or explicitly accepted with sign-off.

**Completion signal**: Commit(s): `fix: address review feedback for GH-25`

### Phase 7: Finalize and Release

**Goal**: Prepare for merge/release with versioning and operational readiness.

**Tasks**:

- [ ] Bump version according to repo conventions for a **minor** impact.
- [ ] Ensure the migration seeds "default" deterministically across environments.
- [ ] Final spec reconciliation (confirm OQs resolved or explicitly tracked).
- [ ] Verify rollout notes (maintenance window + rollback) are accurate.

**Acceptance Criteria**:

- Must: Version bump applied and consistent with release tooling.
- Must: Migration + API behavior matches spec (status codes, defaults, protections).

**Completion signal**: Commit: `chore(release): bump version for GH-25`

## Test Scenarios

1. **Namespace CRUD happy path**: create → list → get → update → delete (when unreferenced).
2. **Slug conflict**: create namespace with existing slug → HTTP 409.
3. **Delete protections**:
   - delete referenced namespace → HTTP 409
   - delete `default` namespace → rejected (per final decision; spec expects protection)
4. **Header resolution**:
   - missing header → resolves to `default`
   - empty header → resolves to `default`
   - invalid slug format → HTTP 422
   - unknown slug → HTTP 404 `{"detail": "Namespace not found"}`
5. **Agent visibility**:
   - with header `team-alpha` → list/get only team-alpha agents
   - with header `team-beta` attempting to get team-alpha agent → 404 (or per OQ-1 decision)
6. **Migration**:
   - upgrade creates table, seeds default, back-fills agents, enforces NOT NULL
   - re-run/second application is a no-op (idempotent)
7. **Orchestrator validation**:
   - all pipeline agents same namespace → passes
   - mixed namespaces → HTTP 422 with clear message

## Artifacts and Links

- Change spec: `doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-spec.md`
- Related epic reference (from spec): GH-24 (Namespace epic)

## Plan Revision Log

- 2026-05-01T15:13:16Z — Initial plan created from spec v0.2.

## Execution Log

- (empty) — To be populated during `/run-plan GH-25` with timestamps, commands executed, and commit SHAs per phase.
