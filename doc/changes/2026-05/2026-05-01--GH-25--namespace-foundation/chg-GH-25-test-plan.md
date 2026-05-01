---
id: chg-GH-25-test-plan
status: Proposed
created: 2026-05-01T00:00:00Z
last_updated: 2026-05-01T00:00:00Z
owners: [mbensass]
service: core-platform
labels: [namespace, multi-tenancy, data-model, api, migration]
links:
  change_spec: doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: minor
summary: >-
  Validate introduction of first-class Namespace scoping: CRUD API, X-Namespace request
  resolution (default fallback + 404 on miss), schema/migration back-fill for nine models,
  and backward compatibility (no access control).
---

# Test Plan - Namespace Foundation — First-Class Scoping Primitive for All Registry & Execution Entities

## 1. Scope and Objectives

**In scope**

- Namespace CRUD API (`/api/namespaces`) behavior, including conflict and delete-guard.
- Request-scoped namespace resolution from `X-Namespace` header (slug-based):
  - valid slug resolves
  - missing/empty header falls back to `default`
  - unknown slug returns `404 {"detail":"Namespace not found"}`
- Data model + migration outcomes:
  - new `namespaces` table seeded with `slug="default"`
  - `namespace_id` added to nine entity tables, back-filled, enforced `NOT NULL`
  - migration idempotence (re-run is a no-op)
  - `tenant_id` preserved on `Request` and `Case` as deprecated compatibility field
- Backward compatibility for clients not sending `X-Namespace`.

**Out of scope (explicitly per spec)**

- Access control / RBAC / visibility policies.
- Namespace-scoped filtering for existing list endpoints (deferred).
- UI/frontend namespace selection.

## 2. References

- Change spec: `doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-spec.md`
- Implementation plan: _not present at time of writing_
- Testing strategy: `.ai/rules/testing-strategy.md`

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| ID | Requirement | Covered by | Status |
|---|---|---|---|
| F-1 | Namespace entity lifecycle (CRUD) | TC-NAMESPACE-001..006 | Covered |
| F-2 | `namespace_id` FK on nine models | TC-NAMESPACE-008..011, TC-NAMESPACE-015 | Covered / TODO |
| F-3 | Request-scoped namespace resolution | TC-NAMESPACE-007..009 | Covered |
| F-4 | `X-Namespace` propagation + default fallback | TC-NAMESPACE-007..010 | Covered |
| F-5 | Migration seed/back-fill/NOT NULL | TC-NAMESPACE-011..012 | Covered |
| F-6 | Preserve `tenant_id` on Request/Case | TC-NAMESPACE-013 | Covered |

| AC | Acceptance Criteria | Covered by | Status |
|---|---|---|---|
| AC-F1-1 | POST /api/namespaces persists row and returns 201 + NamespaceRead | TC-NAMESPACE-001 | Covered |
| AC-F1-2 | POST /api/namespaces with duplicate slug returns 409; no dup row | TC-NAMESPACE-002 | Covered |
| AC-F1-3 | DELETE referenced namespace returns 409; not deleted | TC-NAMESPACE-006 | Covered (may require fixture endpoint) |
| AC-F2-1 | After migration: all rows in nine tables have non-null namespace_id == default UUID | TC-NAMESPACE-011 | Covered |
| AC-F2-2 | Create entity with `X-Namespace: team-alpha` persists namespace_id == team-alpha | TC-NAMESPACE-009 | Covered (endpoint-dependent) |
| AC-F3-1 | Valid `X-Namespace` resolves Namespace object for handler | TC-NAMESPACE-009 | Covered (observable via persisted namespace_id) |
| AC-F3-2 | Invalid `X-Namespace` returns 404 {detail: "Namespace not found"} | TC-NAMESPACE-008 | Covered |
| AC-F4-1 | Missing `X-Namespace` resolves to default and request proceeds | TC-NAMESPACE-007 | Covered |
| AC-F4-2 | Clients not sending X-Namespace see no breaking change on existing endpoints | TC-NAMESPACE-010 | Covered (regression) |
| AC-F5-1 | Migration on DB w/ existing rows: all back-filled; namespaces table has exactly one default row | TC-NAMESPACE-011 | Covered |
| AC-F5-2 | Migration run second time: no errors; DB unchanged | TC-NAMESPACE-012 | Covered |
| AC-F6-1 | After migration: Request/Case tenant_id present and values retained | TC-NAMESPACE-013 | Covered |
| AC-NFR-1 | 50 concurrent requests: P95 namespace resolution overhead ≤ 5ms above baseline | TC-NAMESPACE-014 | TODO (perf harness) |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| Interface ID | Description | Covered by | Status |
|---|---|---|---|
| API-1 | POST `/api/namespaces` | TC-NAMESPACE-001..002 | Covered |
| API-2 | GET `/api/namespaces` (limit/offset) | TC-NAMESPACE-003 | Covered |
| API-3 | GET `/api/namespaces/{slug}` | TC-NAMESPACE-004 | Covered |
| API-4 | PUT `/api/namespaces/{slug}` | TC-NAMESPACE-005 | Covered |
| API-5 | DELETE `/api/namespaces/{slug}` | TC-NAMESPACE-006 | Covered |
| DM-1 | `namespaces` table + constraints | TC-NAMESPACE-001, TC-NAMESPACE-011 | Covered |
| DM-2..DM-10 | `namespace_id` FK on nine models | TC-NAMESPACE-009, TC-NAMESPACE-011, TC-NAMESPACE-015 | Covered / TODO |

### 3.3 Non-Functional Coverage (NFR-#)

| NFR | Requirement | Covered by | Status |
|---|---|---|---|
| NFR-1 | Namespace resolution adds ≤ 5ms P99 overhead | TC-NAMESPACE-014 | TODO |
| NFR-2 | Namespace CRUD endpoints performance targets | TC-NAMESPACE-014 | TODO |
| NFR-3 | Migration idempotent | TC-NAMESPACE-012 | Covered |
| NFR-4 | After migration: zero rows have `namespace_id IS NULL` | TC-NAMESPACE-011 | Covered |
| NFR-5 | Zero existing API integration tests fail post-change | TC-NAMESPACE-010 | Covered (via regression suite run) |
| NFR-6 | `namespace_id` columns indexed | TC-NAMESPACE-015 | TODO (DB-specific assertion) |
| NFR-7 | `tenant_id` deprecation documented + no new internal writes | TC-NAMESPACE-013, TC-NAMESPACE-016 | Covered / TODO |

## 4. Test Types and Layers

Aligned to `.ai/rules/testing-strategy.md`:

- **Unit** (`tests/unit/`): pure logic, schema validation (limited applicability here).
- **Integration** (`tests/integration/` and/or `tests/services/`): DB + FastAPI endpoints via `TestClient`; validate persistence and HTTP errors.
- **E2E** (`tests/e2e/`): backend API end-to-end scenarios through HTTP client flows (preferred for namespace header propagation + CRUD paths).
- **Performance** (manual or harness-driven): concurrency/latency checks for namespace resolution and CRUD endpoints.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC ID | Title | Type(s) | Priority | Related IDs |
|---|---|---|---|---|
| TC-NAMESPACE-001 | Create namespace (201 + body) | E2E | High | F-1, AC-F1-1, API-1, DM-1 |
| TC-NAMESPACE-002 | Reject duplicate namespace slug (409) | E2E | High | F-1, AC-F1-2, API-1 |
| TC-NAMESPACE-003 | List namespaces with pagination | E2E | Medium | F-1, API-2 |
| TC-NAMESPACE-004 | Get namespace by slug (200/404) | E2E | Medium | F-1, API-3 |
| TC-NAMESPACE-005 | Update namespace fields; slug immutable | E2E | Medium | F-1, API-4 |
| TC-NAMESPACE-006 | Delete namespace: 204 when unreferenced; 409 when referenced | E2E | High | F-1, AC-F1-3, API-5 |
| TC-NAMESPACE-007 | Missing X-Namespace resolves to default and request proceeds | E2E | High | F-3, F-4, AC-F4-1 |
| TC-NAMESPACE-008 | Unknown X-Namespace returns 404 detail | E2E | High | F-3, AC-F3-2 |
| TC-NAMESPACE-009 | X-Namespace resolves and persisted entities use that namespace_id | E2E | High | F-2, F-3, AC-F2-2, AC-F3-1 |
| TC-NAMESPACE-010 | Legacy clients: existing endpoints work without X-Namespace (no break) | Integration | High | F-4, AC-F4-2, NFR-5 |
| TC-NAMESPACE-011 | Migration seeds default + back-fills nine tables + enforces NOT NULL | Integration | High | F-5, AC-F2-1, AC-F5-1, NFR-4, DM-1..DM-10 |
| TC-NAMESPACE-012 | Migration is idempotent (re-run safe; no state change) | Integration | High | F-5, AC-F5-2, NFR-3 |
| TC-NAMESPACE-013 | tenant_id preserved on Request and Case after migration | Integration | Medium | F-6, AC-F6-1, NFR-7 |
| TC-NAMESPACE-014 | Performance: namespace resolution overhead + CRUD latency targets | Performance, Manual | Low | AC-NFR-1, NFR-1, NFR-2 |
| TC-NAMESPACE-015 | DB indexes exist for namespace_id columns | Integration | Medium | NFR-6, DM-2..DM-10 |
| TC-NAMESPACE-016 | No internal code writes tenant_id (regression/guard) | Unit, Integration | Low | NFR-7 |

### 5.2 Scenario Details

#### TC-NAMESPACE-001 - Create namespace (201 + body)

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, AC-F1-1, API-1, DM-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Application under test is running for E2E, or E2E harness can call the FastAPI app via an HTTP client.

**Steps**:

1. Call `POST /api/namespaces` with body `{name, slug, description?, owner}` using a new slug (e.g., `team-alpha`).
2. Capture the HTTP response.
3. Call `GET /api/namespaces/{slug}` for the created slug.

**Expected Outcome**:

- Step 1 returns HTTP 201 with a `NamespaceRead` body containing non-empty `id`, and matching `name`, `slug`, `owner`, and timestamps.
- Step 3 returns HTTP 200 and the namespace matches what was created.

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

- A namespace with slug `team-alpha` exists.

**Steps**:

1. Call `POST /api/namespaces` with the same `slug: team-alpha`.
2. Call `GET /api/namespaces` and count namespaces with `slug == "team-alpha"`.

**Expected Outcome**:

- Step 1 returns HTTP 409.
- Step 2 confirms only one namespace exists with that slug.

#### TC-NAMESPACE-003 - List namespaces with pagination

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

- Both calls return HTTP 200 and a JSON array.
- The first call returns at most 2 items; the second call returns the next page (no overlap if deterministic ordering is defined; otherwise assert only size constraints and schema validity).

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

- A namespace with slug `team-alpha` exists.

**Steps**:

1. Call `GET /api/namespaces/team-alpha`.
2. Call `GET /api/namespaces/does-not-exist`.

**Expected Outcome**:

- Step 1 returns HTTP 200 with `slug == "team-alpha"`.
- Step 2 returns HTTP 404.

#### TC-NAMESPACE-005 - Update namespace fields; slug immutable

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Medium
**Related IDs**: F-1, API-4
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespaces_api_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- A namespace with slug `team-alpha` exists.

**Steps**:

1. Call `PUT /api/namespaces/team-alpha` with body `{name: "Team Alpha", description: "...", owner: "..."}`.
2. Call `GET /api/namespaces/team-alpha`.
3. (If request schema allows extra fields) attempt to send `slug` in update payload.

**Expected Outcome**:

- Steps 1-2 return HTTP 200 and reflect updated `name/description/owner`.
- Slug remains `team-alpha` (attempted slug change is rejected or ignored as per implementation).

#### TC-NAMESPACE-006 - Delete namespace: 204 when unreferenced; 409 when referenced

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
- Namespace `team-unused` exists and has no referencing entities.
- There exists at least one API endpoint that creates an entity in a namespace via `X-Namespace` (e.g., `POST /api/requests`) and persists a row with `namespace_id`.

**Steps**:

1. Create at least one entity in namespace `team-alpha` by calling an existing entity-create endpoint with header `X-Namespace: team-alpha`.
2. Call `DELETE /api/namespaces/team-alpha`.
3. Call `DELETE /api/namespaces/team-unused`.
4. Call `GET /api/namespaces/team-unused`.

**Expected Outcome**:

- Step 2 returns HTTP 409 and the namespace still exists.
- Step 3 returns HTTP 204.
- Step 4 returns HTTP 404.

**Notes / Clarifications**:

- If no stable entity-create endpoint exists for referencing, implement this test by directly inserting a referencing row via DB fixtures (integration-level), and keep the API-level delete call as the observable behavior.

#### TC-NAMESPACE-007 - Missing X-Namespace resolves to default and request proceeds

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, F-4, AC-F4-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespace_header_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- The `default` namespace exists.
- There exists at least one API endpoint that opts into namespace resolution dependency and performs a successful operation without requiring `X-Namespace` (e.g., creates a Request).

**Steps**:

1. Call a namespaced endpoint without `X-Namespace` header (e.g., `POST /api/requests` with minimal valid body).
2. Fetch the created entity (or inspect persisted data via test fixtures).

**Expected Outcome**:

- Step 1 succeeds (2xx as appropriate).
- The persisted entity has `namespace_id` equal to the `default` namespace UUID.

#### TC-NAMESPACE-008 - Unknown X-Namespace returns 404 detail

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-2
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespace_header_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- There exists at least one API endpoint that opts into namespace resolution dependency.

**Steps**:

1. Call that endpoint with `X-Namespace: nonexistent-slug`.

**Expected Outcome**:

- Response status is HTTP 404.
- Response JSON body equals `{"detail": "Namespace not found"}`.

#### TC-NAMESPACE-009 - X-Namespace resolves and persisted entities use that namespace_id

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, F-3, AC-F2-2, AC-F3-1, DM-2..DM-10
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/test_namespace_header_e2e.py`
**Tags**: @backend, @api, @e2e

**Preconditions**:

- Namespace `team-alpha` exists.
- There exists at least one entity-create endpoint that:
  - opts into namespace resolution dependency, and
  - persists `namespace_id` on the created row.

**Steps**:

1. Call the entity-create endpoint with header `X-Namespace: team-alpha`.
2. Fetch the created entity (or inspect persisted data).

**Expected Outcome**:

- The created entity has `namespace_id` referencing the `team-alpha` namespace (not default).

**Notes / Clarifications**:

- This scenario provides externally observable coverage for “Namespace object is available to handler” (AC-F3-1) by asserting downstream persisted behavior.

#### TC-NAMESPACE-010 - Legacy clients: existing endpoints work without X-Namespace (no break)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, AC-F4-2, NFR-5
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_legacy_without_namespace_header.py`
**Tags**: @backend, @api

**Preconditions**:

- Integration test app/client fixture exists.

**Steps**:

1. Call representative existing endpoints without `X-Namespace` header (e.g., `GET /api/agents`).
2. Assert the calls do not fail due to missing header.
3. Run the full existing integration test suite.

**Expected Outcome**:

- Step 1 returns HTTP 200.
- Step 2 confirms no new required header semantics.
- Step 3 completes without failures.

#### TC-NAMESPACE-011 - Migration seeds default + back-fills nine tables + enforces NOT NULL

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F2-1, AC-F5-1, NFR-4, DM-1..DM-10
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_migration.py`
**Tags**: @backend, @db, @migration

**Preconditions**:

- A database fixture capable of running Alembic migrations exists (SQLite in-memory or PostgreSQL fixture as supported).
- Database seeded with at least one row in each of the nine tables pre-migration (or fixture provides representative rows).

**Steps**:

1. Apply the Alembic migration that introduces namespaces and namespace_id.
2. Query `namespaces` table for rows with `slug == "default"`.
3. For each of the nine entity tables, run `COUNT(*) WHERE namespace_id IS NULL`.
4. For each of the nine entity tables, assert all rows have `namespace_id == <default-uuid>` (for pre-existing rows).
5. Assert `namespace_id` is `NOT NULL` enforced (e.g., insertion of a row without namespace_id fails, or schema inspection confirms NOT NULL).

**Expected Outcome**:

- Exactly one `default` namespace row exists.
- All nine tables have zero rows with `namespace_id IS NULL`.
- All pre-existing rows have `namespace_id` set to the default UUID.
- NOT NULL constraint is enforced.

#### TC-NAMESPACE-012 - Migration is idempotent (re-run safe; no state change)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, AC-F5-2, NFR-3
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_migration.py`
**Tags**: @backend, @db, @migration

**Preconditions**:

- Migration can be executed twice in the chosen test environment.

**Steps**:

1. Apply migration once.
2. Capture a small set of invariants (e.g., count of namespaces, counts per table, default UUID value).
3. Apply the migration a second time (or execute the same upgrade step again in a controlled harness).
4. Re-check invariants.

**Expected Outcome**:

- No errors are raised on the second run.
- Invariants are unchanged.

#### TC-NAMESPACE-013 - tenant_id preserved on Request and Case after migration

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-6, AC-F6-1, NFR-7, DM-7, DM-8
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_migration.py`
**Tags**: @backend, @db, @migration

**Preconditions**:

- Pre-migration DB contains at least one `Request` and one `Case` row with a non-empty `tenant_id` value.

**Steps**:

1. Apply migration.
2. Query migrated `Request` and `Case` rows.

**Expected Outcome**:

- `tenant_id` column still exists on both tables.
- Values match the pre-migration values.

#### TC-NAMESPACE-014 - Performance: namespace resolution overhead + CRUD latency targets

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: AC-NFR-1, NFR-1, NFR-2
**Test Type(s)**: Performance, Manual
**Automation Level**: Semi-automated
**Target Layer / Location**: Manual runbook (see Section 6)
**Tags**: @backend, @api, @perf

**Preconditions**:

- A runnable environment representative enough to measure latency (local or staging).
- Ability to generate 50 concurrent requests.

**Steps**:

1. Measure baseline latency (P95/P99) for a representative endpoint **without** namespace resolution (or with resolution disabled if a control is available).
2. Measure latency for the same endpoint **with** `X-Namespace: team-alpha` resolution enabled.
3. Measure P50/P95 for namespace CRUD endpoints under 50 concurrent requests.

**Expected Outcome**:

- Overhead attributable to namespace resolution is within thresholds (≤ 5ms at P95/P99 per AC/NFR).
- CRUD endpoints meet targets (P50 < 50ms, P95 < 200ms).

**Notes / Clarifications**:

- If no perf harness exists in-repo, keep this as a manual gate and track tooling needs in Open Questions.

#### TC-NAMESPACE-015 - DB indexes exist for namespace_id columns

**Scenario Type**: Regression
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-6, DM-2..DM-10
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/test_namespace_schema_indexes.py`
**Tags**: @backend, @db

**Preconditions**:

- Test DB supports index inspection (prefer PostgreSQL).

**Steps**:

1. Inspect DB metadata for each of the nine tables.
2. Assert an index exists on `namespace_id` (name may vary).

**Expected Outcome**:

- All nine `namespace_id` columns have an index.

**Notes / Clarifications**:

- If the repository test DB is SQLite-only, add a PostgreSQL-based CI job/fixture for this check or mark as TODO with a clear owner.

#### TC-NAMESPACE-016 - No internal code writes tenant_id (regression/guard)

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-7
**Test Type(s)**: Unit, Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/test_tenant_id_not_written.py` and/or `tests/integration/test_request_case_tenant_id_compat.py`
**Tags**: @backend

**Preconditions**:

- A representative code path exists that creates `Request` and `Case` rows.

**Steps**:

1. Create Request/Case via service/API.
2. Assert `tenant_id` remains unchanged from compatibility defaulting rules (if any) and is not used for scoping decisions.

**Expected Outcome**:

- No Orkestra-internal create/update path writes `tenant_id` as part of namespace scoping.

## 6. Environments and Test Data

**Automated tests (default)**

- `pytest` + async support as per `.ai/rules/testing-strategy.md`.
- DB: SQLite in-memory for integration tests where possible.

**DB-dependent tests (recommended)**

- Migration + index verification are most reliable on PostgreSQL (target DB in spec).
- Test data should include:
  - one pre-existing row in each of the nine tables (to validate migration back-fill)
  - non-default namespace (e.g., `team-alpha`) for header resolution
  - at least one referencing entity row for delete-409 scenario

## 7. Automation Plan and Implementation Mapping

Planned automated coverage (suggested file placement per testing strategy):

- `tests/e2e/test_namespaces_api_e2e.py`: TC-NAMESPACE-001..006
- `tests/e2e/test_namespace_header_e2e.py`: TC-NAMESPACE-007..009
- `tests/integration/test_legacy_without_namespace_header.py`: TC-NAMESPACE-010
- `tests/integration/test_namespace_migration.py`: TC-NAMESPACE-011..013
- `tests/integration/test_namespace_schema_indexes.py`: TC-NAMESPACE-015
- `tests/unit/test_tenant_id_not_written.py` (or integration equivalent): TC-NAMESPACE-016

Manual/semi-automated:

- TC-NAMESPACE-014: performance checks (tooling TBD)

## 8. Risks, Assumptions, and Open Questions

**Assumptions (from spec context)**

- Namespace is purely logical (no RBAC) — tests must not assume permission boundaries.
- Header resolution uses slug with fallback to `default`.

**Risks impacting testability**

- Migration behavior may differ between SQLite and PostgreSQL (constraints, index inspection).
- Delete-409 scenario requires a reliable way to create a referencing entity row in a namespace.

**Open Questions (test-plan specific)**

1. **E2E harness location**: Should backend API E2E tests run in `tests/e2e/` against a running service, or should these be implemented as `tests/integration/` using `TestClient` only? (Impacts TC-NAMESPACE-001..009)
2. **Migration test environment**: Do we have a PostgreSQL fixture in CI to validate Alembic migration + constraints + indexes (TC-NAMESPACE-011/012/015), or must these be run manually on staging?
3. **Default namespace deletion guard**: Spec indicates “default” should not be deletable via API; confirm expected HTTP status/behavior so TC-NAMESPACE-006 can assert it explicitly.
4. **Metrics verification**: Is there an existing `/metrics` endpoint and test harness to validate `orkestra_namespace_resolution_total{result=...}` increments? If yes, add an automated scenario; if not, record as follow-up.
5. (From spec OQ-1) Should `RunNode` receive `namespace_id`, or is it scoped via `Run`? If the decision changes, extend DM coverage and migration tests.

## 9. Plan Revision Log

| Version | Date (UTC) | Author | Notes |
|---|---|---|---|
| 0.1 | 2026-05-01 | mbensass | Initial test plan (no implementation plan present yet). |

## 10. Test Execution Log

| Date (UTC) | Executor | Environment | Scope (TCs) | Result | Notes / Links |
|---|---|---|---|---|---|
