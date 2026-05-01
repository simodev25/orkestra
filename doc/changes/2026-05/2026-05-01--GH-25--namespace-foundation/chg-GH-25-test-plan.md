---
id: chg-GH-25-test-plan
status: Updated
created: 2026-05-01T00:00:00Z
last_updated: 2026-05-01T15:26:39Z
owners: [mbensass]
service: core-platform
labels: [namespace, data-model, api, migration, agents]
links:
  change_spec: doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: minor
summary: >-
  Validate introduction of a first-class Namespace model and request-scoped namespace
  resolution via X-Namespace (default fallback + 404 on miss), with namespace_id added
  ONLY to AgentDefinition, agent list/get filtering by namespace, migration seed/back-fill
  + idempotence, and orchestrator same-namespace validation for pipeline_agent_ids.
---

# Test Plan - Namespace Foundation — Logical Grouping Primitive for Agent Definitions

## 1. Scope and Objectives

**In scope**

- Namespace CRUD API (`/api/namespaces`) behavior:
  - create, list (limit/offset), get-by-slug, update (slug immutable), delete
  - duplicate slug conflict (409)
  - delete blocked when referenced by AgentDefinition (409)
  - default namespace deletion protection (expected rejection; exact status TBD per OQ-2)
- Request-scoped namespace resolution from `X-Namespace` header:
  - valid slug resolves
  - missing/empty header falls back to `default`
  - unknown slug returns `404 {"detail": "Namespace not found"}`
- Agent endpoints are namespace-filtered:
  - `GET /api/agents` returns only agents in the resolved namespace
  - `GET /api/agents/{id}` returns 404 if agent exists but is in a different namespace
- Data model + migration outcomes:
  - new `namespaces` table seeded with `slug="default"` (fixed deterministic UUID)
  - `AgentDefinition.namespace_id` added, back-filled, enforced `NOT NULL`
  - migration is idempotent
  - MCPs, skills, families, workflows, and execution entities remain global (no `namespace_id`)
- Orchestrator validation:
  - rejects cross-namespace `pipeline_agent_ids` (HTTP 422 with descriptive error)
  - accepts same-namespace `pipeline_agent_ids`

**Out of scope (explicitly per spec)**

- Access control / RBAC / visibility policies.
- Namespace-scoped filtering on endpoints other than agent list/get.
- UI/frontend namespace selection.
- Adding `namespace_id` to MCPs, skills, families, workflows, requests, cases, orchestration plans, or runs.

## 2. References

- Change spec: `doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-spec.md`
- Implementation plan: _not present_
- Testing strategy: `.ai/rules/testing-strategy.md`

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| ID | Capability | Covered by | Status |
|---|---|---|---|
| F-1 | Namespace entity lifecycle (create, read, update, delete) | TC-NAMESPACE-001..006 | Covered |
| F-2 | `namespace_id` FK on `AgentDefinition` only | TC-NAMESPACE-009, TC-NAMESPACE-011, TC-NAMESPACE-013 | Covered |
| F-3 | Request-scoped namespace context resolution | TC-NAMESPACE-007..010, TC-NAMESPACE-016 | Covered |
| F-4 | `X-Namespace` propagation with `default` fallback | TC-NAMESPACE-007 | Covered |
| F-5 | Agent list and get endpoints filtered by namespace | TC-NAMESPACE-007, TC-NAMESPACE-010, TC-NAMESPACE-016 | Covered |
| F-6 | Migration: seed default, back-fill agents, enforce NOT NULL | TC-NAMESPACE-011..012 | Covered |
| F-7 | Orchestrator same-namespace validation for `pipeline_agent_ids` | TC-NAMESPACE-017..018 | Covered |

| AC | Acceptance Criteria | Covered by | Status |
|---|---|---|---|
| AC-F1-1 | POST /api/namespaces persists row and returns 201 + NamespaceRead | TC-NAMESPACE-001 | Covered |
| AC-F1-2 | Duplicate slug returns 409; no duplicate row | TC-NAMESPACE-002 | Covered |
| AC-F1-3 | DELETE referenced namespace returns 409; not deleted | TC-NAMESPACE-006 | Covered |
| AC-F2-1 | After migration: every agent row has namespace_id == default UUID | TC-NAMESPACE-011 | Covered |
| AC-F2-2 | Create agent with X-Namespace: team-alpha persists namespace_id == team-alpha | TC-NAMESPACE-009 | Covered |
| AC-F2-3 | Non-agent tables have no namespace_id column | TC-NAMESPACE-013 | Covered |
| AC-F3-1 | Valid X-Namespace resolves Namespace object for handler | TC-NAMESPACE-009, TC-NAMESPACE-010 | Covered |
| AC-F3-2 | Invalid X-Namespace returns 404 with {detail: "Namespace not found"} | TC-NAMESPACE-008 | Covered |
| AC-F4-1 | Missing X-Namespace resolves to default and request proceeds | TC-NAMESPACE-007 | Covered |
| AC-F4-2 | Legacy clients without X-Namespace: GET /api/agents returns only default agents; schema unchanged | TC-NAMESPACE-007 | Covered |
| AC-F5-1 | GET /api/agents with X-Namespace returns only agents in that namespace | TC-NAMESPACE-010 | Covered |
| AC-F5-2 | Cross-namespace GET /api/agents/{id} returns 404 | TC-NAMESPACE-016 | Covered |
| AC-F6-1 | Migration on DB with existing agents: back-filled; namespaces contains default row | TC-NAMESPACE-011 | Covered |
| AC-F6-2 | Migration run second time: no errors; state unchanged | TC-NAMESPACE-012 | Covered |
| AC-F7-1 | Orchestrator rejects cross-namespace pipeline_agent_ids with 422 | TC-NAMESPACE-017 | Covered |
| AC-F7-2 | Orchestrator accepts same-namespace pipeline_agent_ids | TC-NAMESPACE-018 | Covered |
| AC-NFR-1 | 50 concurrent requests: P95 namespace resolution overhead ≤ 5 ms above baseline | TC-NAMESPACE-014 | TODO |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| Interface ID | Description | Covered by | Status |
|---|---|---|---|
| API-1 | POST `/api/namespaces` | TC-NAMESPACE-001..002 | Covered |
| API-2 | GET `/api/namespaces` | TC-NAMESPACE-003 | Covered |
| API-3 | GET `/api/namespaces/{slug}` | TC-NAMESPACE-004 | Covered |
| API-4 | PUT `/api/namespaces/{slug}` | TC-NAMESPACE-005 | Covered |
| API-5 | DELETE `/api/namespaces/{slug}` | TC-NAMESPACE-006 | Covered |
| API-6 | GET `/api/agents` | TC-NAMESPACE-007, TC-NAMESPACE-008, TC-NAMESPACE-010 | Covered |
| API-7 | GET `/api/agents/{id}` | TC-NAMESPACE-009, TC-NAMESPACE-016 | Covered |
| DM-1 | `namespaces` table (new) | TC-NAMESPACE-001, TC-NAMESPACE-011 | Covered |
| DM-2 | `AgentDefinition.namespace_id` (NOT NULL FK + index) | TC-NAMESPACE-011, TC-NAMESPACE-015 | Covered / TODO |
| DM-3..DM-10 | Global resources unchanged (no namespace_id column) | TC-NAMESPACE-013 | Covered |

### 3.3 Non-Functional Coverage (NFR-#)

| NFR | Requirement | Covered by | Status |
|---|---|---|---|
| NFR-1 | Namespace resolution adds ≤ 5 ms P99 overhead per request | TC-NAMESPACE-014 | TODO |
| NFR-2 | Namespace CRUD endpoints: P50 < 50 ms, P95 < 200 ms under 50 concurrent | TC-NAMESPACE-014 | TODO |
| NFR-3 | Migration is idempotent | TC-NAMESPACE-012 | Covered |
| NFR-4 | After migration: zero AgentDefinition rows have `namespace_id IS NULL` | TC-NAMESPACE-011 | Covered |
| NFR-5 | Zero existing API integration tests fail post-change | TC-NAMESPACE-007 | Covered (regression suite run) |
| NFR-6 | `agent_definitions.namespace_id` is indexed | TC-NAMESPACE-015 | TODO (DB-dependent) |

## 4. Test Types and Layers

Aligned to `.ai/rules/testing-strategy.md`:

- **Unit** (`tests/unit/`): pure logic without I/O (minimal for this change).
- **Integration** (`tests/integration/` or `tests/services/`): SQLite in-memory DB + FastAPI endpoints via `httpx.TestClient`; validate HTTP flows, persistence, and schema constraints.
- **E2E** (`tests/e2e/`): backend API end-to-end scenarios through real HTTP calls against a running test app/service (or the project’s established E2E harness); validate externally observable behavior for namespace header propagation + orchestrator validation.
- **Performance**: semi-automated/manual latency + concurrency checks (NFR-1/NFR-2).

## 5. Test Scenarios

### 5.1 Scenario Index

| TC ID | Title | Type(s) | Priority | Related IDs |
|---|---|---|---|---|
| TC-NAMESPACE-001 | Create namespace (201 + body) | E2E | High | F-1, AC-F1-1, API-1 |
| TC-NAMESPACE-002 | Reject duplicate namespace slug (409) | E2E | High | F-1, AC-F1-2, API-1 |
| TC-NAMESPACE-003 | List namespaces with pagination (limit/offset) | E2E | Medium | F-1, API-2 |
| TC-NAMESPACE-004 | Get namespace by slug (200/404) | E2E | Medium | F-1, API-3 |
| TC-NAMESPACE-005 | Update namespace name/description; slug immutable | E2E | Medium | F-1, API-4 |
| TC-NAMESPACE-006 | Delete namespace: 204 unreferenced; 409 referenced; protect default | E2E | High | F-1, AC-F1-3, API-5 |
| TC-NAMESPACE-007 | Legacy client: GET /api/agents without X-Namespace scopes to default | E2E | High | F-4, F-5, AC-F4-1, AC-F4-2, API-6, NFR-5 |
| TC-NAMESPACE-008 | Unknown X-Namespace returns 404 with exact detail | E2E | High | F-3, AC-F3-2, API-6 |
| TC-NAMESPACE-009 | Create agent with X-Namespace persists namespace_id | E2E | High | F-2, F-3, AC-F2-2, AC-F3-1, API-7, DM-2 |
| TC-NAMESPACE-010 | Agent list filtered by X-Namespace | E2E | High | F-5, AC-F5-1, API-6 |
| TC-NAMESPACE-011 | Migration: seed default + back-fill AgentDefinition + NOT NULL | Integration | High | F-6, AC-F2-1, AC-F6-1, NFR-4, DM-1, DM-2 |
| TC-NAMESPACE-012 | Migration idempotence (second run is no-op) | Integration | High | F-6, AC-F6-2, NFR-3 |
| TC-NAMESPACE-013 | Schema guard: global resources have no namespace_id column | Integration | High | AC-F2-3, DM-3..DM-10 |
| TC-NAMESPACE-014 | Performance: namespace resolution overhead + CRUD latency targets | Performance, Manual | Low | AC-NFR-1, NFR-1, NFR-2 |
| TC-NAMESPACE-015 | DB index exists for agent_definitions.namespace_id | Integration | Medium | NFR-6, DM-2 |
| TC-NAMESPACE-016 | Cross-namespace GET /api/agents/{id} returns 404 | E2E | High | F-5, AC-F5-2, API-7 |
| TC-NAMESPACE-017 | Orchestrator rejects cross-namespace pipeline_agent_ids (422) | E2E | High | F-7, AC-F7-1 |
| TC-NAMESPACE-018 | Orchestrator accepts same-namespace pipeline_agent_ids | E2E | High | F-7, AC-F7-2 |

### 5.2 Scenario Details

#### TC-NAMESPACE-001 - Create namespace (201 + body)

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-1, API-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- API is available to accept namespace CRUD requests.

**Steps**:

1. Call `POST /api/namespaces` with `{name: "Team Alpha", slug: "team-alpha", description: "..."}`.
2. Capture response.
3. Call `GET /api/namespaces/team-alpha`.

**Expected Outcome**:

- Step 1 returns HTTP 201 with `NamespaceRead` including `id`, `name`, `slug`, `description` (or null), `created_at`, `updated_at`.
- Step 3 returns HTTP 200 and matches the created namespace.

#### TC-NAMESPACE-002 - Reject duplicate namespace slug (409)

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: High
**Related IDs**: F-1, AC-F1-2, API-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace with slug `team-alpha` exists.

**Steps**:

1. Call `POST /api/namespaces` again with `slug: "team-alpha"`.
2. Call `GET /api/namespaces` and count items with `slug == "team-alpha"`.

**Expected Outcome**:

- Step 1 returns HTTP 409.
- Step 2 confirms exactly one namespace exists with slug `team-alpha`.

#### TC-NAMESPACE-003 - List namespaces with pagination (limit/offset)

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: F-1, API-2
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- At least 3 namespaces exist (including `default`).

**Steps**:

1. Call `GET /api/namespaces?limit=2&offset=0`.
2. Call `GET /api/namespaces?limit=2&offset=2`.

**Expected Outcome**:

- Both calls return HTTP 200 and a JSON list of `NamespaceRead`.
- Each page returns at most `limit` items.

#### TC-NAMESPACE-004 - Get namespace by slug (200/404)

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-1, API-3
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.

**Steps**:

1. Call `GET /api/namespaces/team-alpha`.
2. Call `GET /api/namespaces/does-not-exist`.

**Expected Outcome**:

- Step 1 returns HTTP 200 and `slug == "team-alpha"`.
- Step 2 returns HTTP 404.

#### TC-NAMESPACE-005 - Update namespace name/description; slug immutable

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: F-1, API-4
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.

**Steps**:

1. Call `PUT /api/namespaces/team-alpha` with `{name: "Team Alpha Updated", description: "Updated"}`.
2. Call `GET /api/namespaces/team-alpha`.
3. Attempt to change slug (send `slug` in update payload if the API accepts unknown fields).

**Expected Outcome**:

- Steps 1-2 return HTTP 200 and reflect updated `name/description`.
- Slug remains `team-alpha`.

#### TC-NAMESPACE-006 - Delete namespace: 204 unreferenced; 409 referenced; protect default

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-3, API-5
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- Namespace `team-unused` exists and has no referencing agents.
- At least one agent exists in `team-alpha`.

**Steps**:

1. Call `DELETE /api/namespaces/team-alpha`.
2. Call `DELETE /api/namespaces/team-unused`.
3. Call `GET /api/namespaces/team-unused`.
4. Call `DELETE /api/namespaces/default`.

**Expected Outcome**:

- Step 1 returns HTTP 409 and the namespace still exists.
- Step 2 returns HTTP 204.
- Step 3 returns HTTP 404.
- Step 4 rejects deletion of `default` (exact status/message TBD; see Section 8 / OQ-2).

#### TC-NAMESPACE-007 - Legacy client: GET /api/agents without X-Namespace scopes to default

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, F-5, AC-F4-1, AC-F4-2, API-6, NFR-5
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_agents_namespace_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- At least one agent exists in `default`.
- At least one agent exists in a non-default namespace (e.g., `team-alpha`).

**Steps**:

1. Call `GET /api/agents` with **no** `X-Namespace` header.
2. Call `GET /api/agents` with `X-Namespace` header present but empty.
3. Validate response body is a list of AgentRead items.

**Expected Outcome**:

- Step 1 returns HTTP 200.
- Step 2 returns HTTP 200.
- Response includes only agents in the `default` namespace.
- Response shape remains backward compatible for clients that do not send `X-Namespace`.

#### TC-NAMESPACE-008 - Unknown X-Namespace returns 404 with exact detail

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-2, API-6
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_agents_namespace_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Agent list endpoint uses the namespace resolution dependency.

**Steps**:

1. Call `GET /api/agents` with `X-Namespace: nonexistent-slug`.

**Expected Outcome**:

- Response status is HTTP 404.
- Response JSON body equals `{"detail": "Namespace not found"}`.

#### TC-NAMESPACE-009 - Create agent with X-Namespace persists namespace_id

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, F-3, AC-F2-2, AC-F3-1, API-7, DM-2
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_agents_namespace_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- Agent create endpoint `POST /api/agents` exists.

**Steps**:

1. Call `POST /api/agents` with a minimal valid agent payload and header `X-Namespace: team-alpha`.
2. Capture created agent `id`.
3. Call `GET /api/agents/{id}` with header `X-Namespace: team-alpha`.

**Expected Outcome**:

- Step 1 succeeds (2xx/201 per current contract).
- Step 3 returns HTTP 200 and the returned agent has `namespace_id` referencing `team-alpha` (not `default`).

#### TC-NAMESPACE-010 - Agent list filtered by X-Namespace

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-1, API-6
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_agents_namespace_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- Namespace `team-beta` exists.
- At least one agent exists in each namespace.

**Steps**:

1. Call `GET /api/agents` with `X-Namespace: team-alpha`.
2. Call `GET /api/agents` with `X-Namespace: team-beta`.

**Expected Outcome**:

- Step 1 returns HTTP 200 and includes only `team-alpha` agents.
- Step 2 returns HTTP 200 and includes only `team-beta` agents.

#### TC-NAMESPACE-011 - Migration: seed default + back-fill AgentDefinition + NOT NULL

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-6, AC-F2-1, AC-F6-1, NFR-4, DM-1, DM-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_migration.py`
**Tags**: @backend, @db, @migration

**Preconditions**:

- A test DB fixture can apply Alembic migrations.
- Pre-migration DB contains at least one `AgentDefinition` row.

**Steps**:

1. Apply the Alembic migration that introduces `namespaces` and `agent_definitions.namespace_id`.
2. Query `namespaces` for `slug == "default"`.
3. Query `agent_definitions` and assert `COUNT(*) WHERE namespace_id IS NULL == 0`.
4. Assert pre-existing agent rows have `namespace_id == <default-uuid>`.
5. Assert `agent_definitions.namespace_id` is `NOT NULL` enforced.

**Expected Outcome**:

- Exactly one `default` namespace row exists.
- No agent rows have `namespace_id IS NULL`.
- All pre-existing agents are back-filled to the default UUID.
- NOT NULL is enforced.

#### TC-NAMESPACE-012 - Migration idempotence (second run is no-op)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-6, AC-F6-2, NFR-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_migration.py`
**Tags**: @backend, @db, @migration

**Preconditions**:

- Migration harness can attempt a second upgrade run safely.

**Steps**:

1. Apply migration once.
2. Capture invariants: default namespace row (id/slug), agent counts, and `COUNT(*) WHERE namespace_id IS NULL`.
3. Apply migration a second time (or run the same upgrade step again in a controlled harness).
4. Re-check invariants.

**Expected Outcome**:

- No errors on the second run.
- Invariants are unchanged.

#### TC-NAMESPACE-013 - Schema guard: global resources have no namespace_id column

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: AC-F2-3, DM-3, DM-4, DM-5, DM-6, DM-7, DM-8, DM-9, DM-10
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_schema_global_resources.py`
**Tags**: @backend, @db

**Preconditions**:

- Migration has been applied.

**Steps**:

1. Inspect schema for: `mcp_definitions`, `family_definitions`, `skill_definitions`, `workflow_definitions`, `requests`, `cases`, `orchestration_plans`, `runs`.
2. Assert none of these tables have a `namespace_id` column.

**Expected Outcome**:

- No listed global table contains `namespace_id`.

#### TC-NAMESPACE-014 - Performance: namespace resolution overhead + CRUD latency targets

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: AC-NFR-1, NFR-1, NFR-2
**Test Type(s)**: Performance
**Automation Level**: Semi-automated
**Target Layer / Location**: Manual runbook (see Section 6)
**Tags**: @backend, @api, @perf

**Preconditions**:

- Runnable environment representative enough to measure latency.
- Tooling to generate 50 concurrent requests.

**Steps**:

1. Measure baseline latency (P95/P99) for `GET /api/agents` without `X-Namespace`.
2. Measure latency (P95/P99) for `GET /api/agents` with `X-Namespace: team-alpha`.
3. Under 50 concurrent requests, measure P50/P95 for namespace CRUD endpoints.

**Expected Outcome**:

- Overhead attributable to namespace resolution meets thresholds.
- CRUD endpoints meet latency thresholds.

#### TC-NAMESPACE-015 - DB index exists for agent_definitions.namespace_id

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-6, DM-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_schema_indexes.py`
**Tags**: @backend, @db

**Preconditions**:

- Migration has been applied.
- Test DB supports index inspection.

**Steps**:

1. Inspect indexes for `agent_definitions`.
2. Assert at least one index exists that covers `namespace_id`.

**Expected Outcome**:

- `agent_definitions.namespace_id` is indexed.

#### TC-NAMESPACE-016 - Cross-namespace GET /api/agents/{id} returns 404

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-2, API-7
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_agents_namespace_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- Namespace `team-beta` exists.
- An agent exists in `team-alpha`.

**Steps**:

1. Call `GET /api/agents/{id}` for the team-alpha agent with `X-Namespace: team-beta`.

**Expected Outcome**:

- Response status is HTTP 404.

**Notes / Clarifications** (optional):

- This follows AC-F5-2. If product decision changes to 403, update this scenario accordingly (spec OQ-1).

#### TC-NAMESPACE-017 - Orchestrator rejects cross-namespace pipeline_agent_ids (422)

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-7, AC-F7-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_orchestrator_namespace_validation_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- Namespace `team-beta` exists.
- One agent exists in each namespace.

**Steps**:

1. Call the orchestration plan creation endpoint with `pipeline_agent_ids` containing one team-alpha agent and one team-beta agent.

**Expected Outcome**:

- Response status is HTTP 422.
- Response contains a descriptive message indicating all pipeline agents must belong to the same namespace.

#### TC-NAMESPACE-018 - Orchestrator accepts same-namespace pipeline_agent_ids

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-7, AC-F7-2
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_orchestrator_namespace_validation_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- At least two agents exist in `team-alpha`.

**Steps**:

1. Call the orchestration plan creation endpoint with `pipeline_agent_ids` containing only team-alpha agents.

**Expected Outcome**:

- Request succeeds (2xx per API contract).
- Plan is created successfully.

## 6. Environments and Test Data

**Automated tests (default)**

- Test runner: `pytest` (+ `pytest-asyncio` where needed).
- Integration DB: SQLite in-memory (per `.ai/rules/testing-strategy.md`).
- HTTP tests: `httpx.TestClient` (per strategy) for integration tests; E2E harness per project convention.

**Test data requirements**

- Namespaces: ensure `default` plus at least `team-alpha` and `team-beta`.
- Agents:
  - at least one agent in `default`
  - at least one agent in `team-alpha`
  - at least one agent in `team-beta`
- Orchestrator:
  - identify the orchestration plan creation endpoint and minimal request body required to set `pipeline_agent_ids`.

## 7. Automation Plan and Implementation Mapping

Suggested placement per testing strategy:

- `tests/e2e/test_namespaces_api_e2e.py`: TC-NAMESPACE-001..006
- `tests/e2e/test_agents_namespace_e2e.py`: TC-NAMESPACE-007..010, TC-NAMESPACE-016
- `tests/e2e/test_orchestrator_namespace_validation_e2e.py`: TC-NAMESPACE-017..018
- `tests/integration/test_namespace_migration.py`: TC-NAMESPACE-011..012
- `tests/integration/test_namespace_schema_global_resources.py`: TC-NAMESPACE-013
- `tests/integration/test_namespace_schema_indexes.py`: TC-NAMESPACE-015

Manual / semi-automated:

- TC-NAMESPACE-014: performance checks (tooling TBD).

## 8. Risks, Assumptions, and Open Questions

**Assumptions (from spec)**

- Namespaces are globally readable (no RBAC).
- `X-Namespace` resolves by slug; missing/empty falls back to `default`.

**Risks impacting testability**

- Migration and index assertions may differ between SQLite and PostgreSQL (target DB is PostgreSQL 16 in spec).
- Orchestrator endpoint contract may require additional fields beyond `pipeline_agent_ids`, affecting E2E setup.

**Open Questions (from spec + test-plan needs)**

- OQ-1: For cross-namespace `GET /api/agents/{id}`, should the API return 404 or 403? (AC currently specifies 404.)
- OQ-2: Exact expected status/message for attempting to delete the `default` namespace.
- OQ-3: If a slug fails regex validation (header or body), what HTTP status/body should be returned?
- OQ-4: Should orchestrator same-namespace validation apply to other agent references beyond `pipeline_agent_ids`?
- Confirm the canonical orchestration plan creation endpoint and minimal payload needed to exercise AC-F7-1/2.

## 9. Plan Revision Log

| Version | Date (UTC) | Author | Notes |
|---|---|---|---|
| 0.1 | 2026-05-01 | mbensass | Initial test plan draft. |
| 0.2 | 2026-05-01 | mbensass | Updated to align with spec: namespace_id only on AgentDefinition; added agent list/get filtering and orchestrator same-namespace validation; removed incorrect references to namespacing other models. |

## 10. Test Execution Log

| Date (UTC) | Executor | Environment | Scope (TCs) | Result | Notes / Links |
|---|---|---|---|---|---|
