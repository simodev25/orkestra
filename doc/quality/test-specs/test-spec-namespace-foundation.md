---
id: TEST-namespace-foundation
status: Current
version: 1.0.0
last_updated: 2026-05-01
links:
  related_changes:
    - GH-25
  related_features:
    - SPEC-namespace-foundation
  source_test_plan: doc/changes/2026-05/2026-05-01--GH-25--namespace-foundation/chg-GH-25-test-plan.md
---

# Test Specification: Namespace Foundation

## Test Strategy

This feature is validated through a multi-layer testing approach:

1. **Unit Tests** (`tests/unit/`): Pure logic validation without I/O
2. **Integration Tests** (`tests/integration/`, `tests/services/`): FastAPI endpoints via `httpx.TestClient` with SQLite in-memory DB
3. **Backend API E2E Tests** (`tests/e2e/`): Full HTTP request/response validation across namespace-scoped operations

## Critical Test Scenarios

### Namespace CRUD: Create (TC-NAMESPACE-001)
**Type**: Happy Path | **Priority**: High | **Layer**: E2E

**Given** a valid namespace creation payload  
**When** `POST /api/namespaces` is called with `{name, slug, description}`  
**Then** the API returns HTTP 201 with a `NamespaceRead` response and the namespace is retrievable via `GET /api/namespaces/{slug}`

**Validates**: F-1, AC-F1-1, API-1

---

### Namespace CRUD: Duplicate Slug Rejection (TC-NAMESPACE-002)
**Type**: Negative | **Priority**: High | **Layer**: E2E

**Given** a namespace with slug `team-alpha` already exists  
**When** `POST /api/namespaces` is called with the same slug  
**Then** the API returns HTTP 409 and no duplicate namespace is created

**Validates**: F-1, AC-F1-2, API-1

---

### Namespace CRUD: Delete Protection for Referenced (TC-NAMESPACE-006)
**Type**: Negative | **Priority**: High | **Layer**: E2E

**Given** a namespace with at least one agent referencing it  
**When** `DELETE /api/namespaces/{slug}` is called  
**Then** the API returns HTTP 409 and the namespace is not deleted

**Validates**: F-1, AC-F1-3, API-5

---

### X-Namespace Header: Default Fallback (TC-NAMESPACE-007)
**Type**: Happy Path | **Priority**: High | **Layer**: E2E

**Given** agents exist in the "default" namespace  
**When** `GET /api/agents` is called without an `X-Namespace` header  
**Then** the API returns HTTP 200 with only agents from the "default" namespace

**Validates**: F-4, F-5, AC-F4-1, AC-F4-2, API-6

---

### X-Namespace Header: Unknown Slug Returns 404 (TC-NAMESPACE-008)
**Type**: Negative | **Priority**: High | **Layer**: E2E

**Given** no namespace with slug `nonexistent-slug` exists  
**When** `GET /api/agents` is called with `X-Namespace: nonexistent-slug`  
**Then** the API returns HTTP 404 with `{"detail": "Namespace not found"}`

**Validates**: F-3, AC-F3-2, API-6

---

### Agent Scoping: Create with X-Namespace (TC-NAMESPACE-009)
**Type**: Happy Path | **Priority**: High | **Layer**: E2E

**Given** a namespace `team-alpha` exists  
**When** `POST /api/agents` is called with `X-Namespace: team-alpha` and a valid agent payload  
**Then** the created agent's `namespace_id` references `team-alpha` (not "default")

**Validates**: F-2, F-3, AC-F2-2, AC-F3-1, API-7, DM-2

---

### Agent Scoping: List Filtered by Namespace (TC-NAMESPACE-010)
**Type**: Happy Path | **Priority**: High | **Layer**: E2E

**Given** agents exist in both `team-alpha` and `team-beta` namespaces  
**When** `GET /api/agents` is called with `X-Namespace: team-alpha`  
**Then** the API returns HTTP 200 with only agents from `team-alpha`

**Validates**: F-5, AC-F5-1, API-6

---

### Agent Scoping: Cross-Namespace Get Returns 404 (TC-NAMESPACE-016)
**Type**: Negative | **Priority**: High | **Layer**: E2E

**Given** an agent exists in namespace `team-alpha`  
**When** `GET /api/agents/{id}` is called with `X-Namespace: team-beta`  
**Then** the API returns HTTP 404 (agent not visible in the requested namespace)

**Validates**: F-5, AC-F5-2, API-7

---

### Migration: Back-Fill and NOT NULL Enforcement (TC-NAMESPACE-011)
**Type**: Happy Path | **Priority**: High | **Layer**: Integration

**Given** a database with pre-existing `AgentDefinition` rows  
**When** the namespace migration is applied  
**Then** all agents have `namespace_id = DEFAULT_NAMESPACE_ID` and zero agents have `namespace_id IS NULL`

**Validates**: F-6, AC-F2-1, AC-F6-1, NFR-4, DM-1, DM-2

---

### Migration: Idempotence (TC-NAMESPACE-012)
**Type**: Regression | **Priority**: High | **Layer**: Integration

**Given** the migration has already been applied  
**When** the migration is run a second time  
**Then** no errors occur and the database state remains unchanged

**Validates**: F-6, AC-F6-2, NFR-3

---

### Schema Guard: Global Resources Unchanged (TC-NAMESPACE-013)
**Type**: Regression | **Priority**: High | **Layer**: Integration

**Given** the migration has been applied  
**When** schema inspection is performed on `mcp_definitions`, `family_definitions`, `skill_definitions`, `workflow_definitions`, `requests`, `cases`, `orchestration_plans`, and `runs`  
**Then** none of these tables have a `namespace_id` column

**Validates**: AC-F2-3, DM-3..DM-10

---

### Orchestrator: Cross-Namespace Rejection (TC-NAMESPACE-017)
**Type**: Negative | **Priority**: High | **Layer**: E2E

**Given** agents exist in both `team-alpha` and `team-beta` namespaces  
**When** an orchestration plan is submitted with `pipeline_agent_ids` referencing agents from both namespaces  
**Then** the API returns HTTP 422 with a message indicating all pipeline agents must belong to the same namespace

**Validates**: F-7, AC-F7-1

---

### Orchestrator: Same-Namespace Acceptance (TC-NAMESPACE-018)
**Type**: Happy Path | **Priority**: High | **Layer**: E2E

**Given** multiple agents exist in `team-alpha` namespace  
**When** an orchestration plan is submitted with `pipeline_agent_ids` referencing only `team-alpha` agents  
**Then** the validation passes and the plan is created successfully

**Validates**: F-7, AC-F7-2

---

## Test Data Requirements

- **Namespaces**: `default` (seeded), `team-alpha`, `team-beta`, `team-unused` (no agents)
- **Agents**: At least one agent in each of `default`, `team-alpha`, and `team-beta`
- **Orchestration Plans**: Minimal valid payload with `pipeline_agent_ids` array

## Performance and Non-Functional Validation

### Namespace Resolution Overhead (TC-NAMESPACE-014)
**Type**: Performance | **Priority**: Low | **Layer**: Manual/Semi-Automated

**Target**: P99 namespace resolution overhead ≤ 5ms above baseline  
**Target**: Namespace CRUD endpoints P50 < 50ms, P95 < 200ms under 50 concurrent requests

**Validates**: AC-NFR-1, NFR-1, NFR-2

---

### Index Presence (TC-NAMESPACE-015)
**Type**: Regression | **Priority**: Medium | **Layer**: Integration

**Given** the migration has been applied  
**When** database schema is inspected  
**Then** an index exists on `agent_definitions.namespace_id`

**Validates**: NFR-6, DM-2

---

## Test Coverage Summary

| Capability | Coverage | Status |
|------------|----------|--------|
| F-1: Namespace CRUD | TC-001, 002, 003, 004, 005, 006 | ✅ Covered |
| F-2: `namespace_id` on AgentDefinition only | TC-009, 011, 013 | ✅ Covered |
| F-3: Request-scoped context resolution | TC-007, 008, 009, 010, 016 | ✅ Covered |
| F-4: X-Namespace header propagation | TC-007 | ✅ Covered |
| F-5: Agent list/get filtering | TC-007, 010, 016 | ✅ Covered |
| F-6: Migration seed/back-fill | TC-011, 012 | ✅ Covered |
| F-7: Orchestrator same-namespace validation | TC-017, 018 | ✅ Covered |

## Automation Status

- **Automated**: TC-001 through TC-013, TC-015 through TC-018 (implemented in integration and E2E test suites)
- **Manual/Semi-Automated**: TC-014 (performance benchmarks)

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0.0 | 2026-05-01 | Initial test specification derived from change test plan (GH-25) |
