---
id: chg-GH-20-test-plan
status: Proposed
created: 2026-04-28T21:06:46Z
last_updated: 2026-04-28T21:06:46Z
owners: [mbensass]
service: agent-registry
labels: [llm, agent-generation, ux, backend, frontend]
links:
  change_spec: doc/changes/2026-04/2026-04-28--GH-20--llm-powered-agent-generation/chg-GH-20-spec.md
  implementation_plan: null
  testing_strategy: .ai/rules/testing-strategy.md
version_impact: minor
summary: Replace heuristic agent-draft generation with a real LLM-backed flow (with fallback), enrich the UI with family/skills selectors, expose source + MCP rationale, and write debug traces.
---

# Test Plan - LLM-Powered Agent Generation

## 1. Scope and Objectives

This test plan covers the change from heuristic/template agent-draft generation to an LLM-backed generation pipeline with a safe fallback, plus corresponding UI updates.

Objectives:

- Validate `POST /api/agents/generate-draft` returns correct `source` values (`llm` vs `heuristic_template`) and always succeeds (HTTP 200) even when the LLM fails.
- Validate the LLM prompt contains the required platform context (MCP catalog, families, skills, similar agents).
- Validate LLM JSON parsing + schema validation and safety corrections (unknown `family_id`).
- Validate debug trace files are written for all LLM call attempts.
- Validate UI intent form enrichment (family selector, skills multi-select) and review-step display (source badge + MCP rationale).

## 2. References

- Change Spec: `doc/changes/2026-04/2026-04-28--GH-20--llm-powered-agent-generation/chg-GH-20-spec.md`
- Testing Strategy: `.ai/rules/testing-strategy.md`
- Interfaces: API-1 (`POST /api/agents/generate-draft`), API-2 (`GET /api/families`), API-3 (`GET /api/skills`)
- Data Model Impact: DM-1 (`preferred_skill_ids` added to request schema)

## 3. Coverage Overview

### 3.1 Functional Coverage (F-#, AC-#)

| Capability / AC | Coverage Status | Test Cases |
|---|---:|---|
| F-1 Real LLM call for agent draft generation | Covered | TC-AGENTGEN-001, TC-AGENTGEN-005 |
| AC-F1-1 (`source="llm"`, non-generic prompt_content) | Covered | TC-AGENTGEN-001 |
| F-2 Full platform context injection into LLM prompt | Covered | TC-AGENTGEN-002 |
| AC-F2-1 (prompt includes MCPs, families, skills, ≤5 similar agents) | Covered | TC-AGENTGEN-002 |
| F-3 Structured JSON response validated against GeneratedAgentDraft | Covered | TC-AGENTGEN-003 |
| AC-F3-1 (valid JSON parsed, required fields non-null) | Covered | TC-AGENTGEN-003 |
| AC-F3-2 (unknown family_id corrected or safe fallback) | Covered | TC-AGENTGEN-004 |
| F-4 Heuristic fallback when LLM is unavailable | Covered | TC-AGENTGEN-005, TC-AGENTGEN-006 |
| AC-F4-1 (LLM unavailable → 200 + heuristic_template + non-empty draft) | Covered | TC-AGENTGEN-005 |
| AC-F4-2 (unparseable JSON → fallback 200 + heuristic_template) | Covered | TC-AGENTGEN-006 |
| F-5 `source` indicator surfaced to frontend | Covered (Manual) | TC-AGENTGEN-012 |
| AC-F5-1 (source badge renders correct copy) | Covered (Manual) | TC-AGENTGEN-012 |
| F-6 Debug trace files for LLM generation calls | Covered | TC-AGENTGEN-007 |
| AC-F6-1 (trace written on success/failure with required fields) | Covered | TC-AGENTGEN-007 |
| F-7 Frontend family selector in intent form | Covered (Manual) | TC-AGENTGEN-010 |
| AC-F7-1 (family dropdown populated; selection sent as preferred_family) | Covered (Manual) | TC-AGENTGEN-010 |
| F-8 Frontend skills multi-select in intent form | Covered (Manual) | TC-AGENTGEN-011 |
| AC-F8-1 (skills multi-select populated; selection sent as preferred_skill_ids) | Covered (Manual) | TC-AGENTGEN-011 |
| F-9 MCP rationale displayed in review step | Covered (Manual) | TC-AGENTGEN-012 |
| AC-F9-1 (each MCP checkbox displays rationale string) | Covered (Manual) | TC-AGENTGEN-012 |
| F-10 Updated UI copy reflecting AI-powered generation | Covered (Manual) | TC-AGENTGEN-012 |

### 3.2 Interface Coverage (API-#, EVT-#, DM-#)

| Interface / Model | Coverage Status | Test Cases |
|---|---:|---|
| API-1 POST `/api/agents/generate-draft` | Covered | TC-AGENTGEN-001, TC-AGENTGEN-005, TC-AGENTGEN-006, TC-AGENTGEN-009 |
| API-2 GET `/api/families` (frontend consumption) | Covered (Manual) | TC-AGENTGEN-010 |
| API-3 GET `/api/skills` (frontend consumption) | Covered (Manual) | TC-AGENTGEN-011 |
| DM-1 `preferred_skill_ids?: string[]` in request schema | Covered | TC-AGENTGEN-009 |
| AC-DM1-1 (preferred_skill_ids accepted + passed to service) | Covered | TC-AGENTGEN-009 |

### 3.3 Non-Functional Coverage (NFR-#)

| NFR | Coverage Status | Test Cases |
|---|---:|---|
| NFR-1 P95 LLM path latency ≤ 30 s | Covered (Manual) | TC-AGENTGEN-013 |
| NFR-2 Fallback path latency ≤ 500 ms | Covered (Manual) | TC-AGENTGEN-013 |
| NFR-3 LLM failures never return 5xx; fallback invoked | Covered | TC-AGENTGEN-005, TC-AGENTGEN-006 |
| AC-NFR3-1 (Timeout/ConnectionError → 200 + heuristic_template) | Covered | TC-AGENTGEN-005 |
| NFR-4 Trace file written for every LLM attempt within ≤ 1 s of response | Covered | TC-AGENTGEN-007 |
| NFR-5 Prompt construction isolated & testable (no DB/I/O deps) | Covered (via unit target) | TC-AGENTGEN-002 |
| NFR-6 LLM call injectable/mockable | Covered (via integration target) | TC-AGENTGEN-005, TC-AGENTGEN-006 |
| NFR-7 Sanitize user-controlled strings before prompt inclusion | Covered | TC-AGENTGEN-008 |

## 4. Test Types and Layers

Aligned to `.ai/rules/testing-strategy.md`:

- **Unit** (`tests/unit/`): prompt building, sanitization, JSON parse/validation, correction rules.
- **Integration** (`tests/integration/` or `tests/services/`): endpoint behavior via FastAPI TestClient / http client; DB-backed fixtures; fallback behavior and trace writing with filesystem isolation.
- **Backend API E2E** (`tests/e2e/`): system-level API verification via real HTTP calls against a running backend service.
- **Manual**: frontend modal behaviors (selectors, badges, rationale display) and latency checks.

## 5. Test Scenarios

### 5.1 Scenario Index

| TC-ID | Title | Type(s) | Priority |
|---|---|---|---|
| TC-AGENTGEN-001 | API E2E: LLM-backed generation returns `source="llm"` and rationale | E2E | High |
| TC-AGENTGEN-002 | Prompt includes full platform context (MCPs, families, skills, similar agents) | Unit | High |
| TC-AGENTGEN-003 | LLM JSON parsed + validated against GeneratedAgentDraft | Unit | High |
| TC-AGENTGEN-004 | Unknown family_id corrected to safe value | Unit | Medium |
| TC-AGENTGEN-005 | Fallback on LLM unavailable/Timeout/ConnectionError returns 200 + heuristic_template | Integration | High |
| TC-AGENTGEN-006 | Fallback on unparseable JSON returns 200 + heuristic_template | Integration | High |
| TC-AGENTGEN-007 | Trace file written for every LLM attempt (success/failure) | Integration | High |
| TC-AGENTGEN-008 | Prompt sanitization strips control chars from user input | Unit | Medium |
| TC-AGENTGEN-009 | Request schema accepts preferred_skill_ids and passes through | Integration | Medium |
| TC-AGENTGEN-010 | UI: family dropdown populated + selection sent as preferred_family | Manual | Medium |
| TC-AGENTGEN-011 | UI: skills multi-select populated + selected IDs sent as preferred_skill_ids | Manual | Medium |
| TC-AGENTGEN-012 | UI: source badge copy + MCP rationale displayed per MCP | Manual | High |
| TC-AGENTGEN-013 | Manual performance checks (LLM path ≤30s; fallback ≤500ms) | Manual | Low |

### 5.2 Scenario Details

#### TC-AGENTGEN-001 - API E2E: LLM-backed generation returns `source="llm"` and rationale

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-1, F-2, F-3, F-5, F-9, API-1, AC-F1-1
**Test Type(s)**: E2E
**Automation Level**: Automated
**Target Layer / Location**: `tests/e2e/` (Backend API E2E)
**Tags**: @backend, @api, @e2e

**Preconditions**:

- A test backend service is running and reachable over HTTP.
- LLM configuration is present and points to a reachable LLM provider (or a test double that returns deterministic JSON).
- The system has at least: one MCP entry, one family, one skill, and at least one existing agent (to allow “similar agents” context).

**Steps**:

1. Send `POST /api/agents/generate-draft` with an intent that clearly references a platform concept (MCP name or known capability) and optional preferred family/skills.
2. Capture HTTP status, response headers, and JSON body.

**Expected Outcome**:

- HTTP 200.
- `source` equals `"llm"`.
- `draft.prompt_content` references the provided intent and includes platform-specific vocabulary (not a generic placeholder-only template).
- `draft.mcp_rationale` is present and non-empty; for each selected MCP there is a rationale string.

**Notes / Clarifications**:

- If the repo does not currently provide a runnable Backend API E2E harness, keep this scenario as the target and implement it once a harness exists; until then, run as a manual E2E by starting the backend locally and calling the endpoint via an HTTP client.

#### TC-AGENTGEN-002 - Prompt includes full platform context (MCPs, families, skills, similar agents)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-2, NFR-5, AC-F2-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- A prompt-building function exists that accepts the request + context objects as inputs.

**Steps**:

1. Build a synthetic context with:
   - MCP catalog entries (≥ 1)
   - Families (≥ 1)
   - Skills (≥ 1)
   - Similar agents list length = 0, 1, and 5 (boundary)
2. Call the prompt builder with a representative request.

**Expected Outcome**:

- The resulting system prompt text includes serialized sections for MCPs, families, skills, and similar agents.
- The similar-agents section includes **no more than 5** summaries.

#### TC-AGENTGEN-003 - LLM JSON parsed + validated against GeneratedAgentDraft

**Scenario Type**: Happy Path
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, AC-F3-1
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- A JSON parsing/validation helper exists for LLM output.

**Steps**:

1. Provide a valid JSON payload representing a minimal-but-valid `GeneratedAgentDraft`.
2. Parse and validate it.

**Expected Outcome**:

- Validation succeeds.
- All required draft fields are non-null.

#### TC-AGENTGEN-004 - Unknown family_id corrected to safe value

**Scenario Type**: Edge Case
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: AC-F3-2
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- A rule exists to correct unknown family IDs before returning the response.

**Steps**:

1. Simulate a parsed LLM draft where `family_id` is an ID not present in the known family list.
2. Apply the correction rule / draft construction step.

**Expected Outcome**:

- The resulting response draft has a `family_id` that is either:
  - a known family ID, or
  - a safe fallback value per service rules (but not an unknown ID).

#### TC-AGENTGEN-005 - Fallback on LLM unavailable/Timeout/ConnectionError returns 200 + heuristic_template

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-4, NFR-3, NFR-6, API-1, AC-F4-1, AC-NFR3-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend, @api

**Preconditions**:

- Integration test can inject/mock the LLM client factory used by the generation service.

**Steps**:

1. Configure the LLM dependency to behave as:
   - not configured, and
   - raising `TimeoutError`, and
   - raising `ConnectionError`.
2. For each case, call `POST /api/agents/generate-draft`.

**Expected Outcome**:

- HTTP 200 for all cases (no 5xx).
- `source` equals `"heuristic_template"`.
- Response contains a non-empty `draft`.

#### TC-AGENTGEN-006 - Fallback on unparseable JSON returns 200 + heuristic_template

**Scenario Type**: Negative
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-3, F-4, API-1, AC-F4-2
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend, @api

**Preconditions**:

- Integration test can force the LLM dependency to return a response that cannot be parsed as JSON.

**Steps**:

1. Arrange the LLM response to be non-JSON (or JSON embedded in surrounding text that fails extraction).
2. Call `POST /api/agents/generate-draft`.

**Expected Outcome**:

- HTTP 200.
- `source` equals `"heuristic_template"`.
- A non-empty draft is returned.

#### TC-AGENTGEN-007 - Trace file written for every LLM attempt (success/failure)

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-6, NFR-4, AC-F6-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend

**Preconditions**:

- Test can set `ORKESTRA_DEBUG_AGENT_GENERATION_DIR` to a temporary directory.

**Steps**:

1. Execute one generation request where the LLM succeeds.
2. Execute one generation request where the LLM fails (exception) and fallback occurs.
3. Inspect the trace directory for newly written JSON trace files.

**Expected Outcome**:

- A trace JSON file is written for each attempt.
- Each trace includes: request payload, injected context, raw LLM output (or error), parsed result (or fallback indication), timestamp, and latency.

#### TC-AGENTGEN-008 - Prompt sanitization strips control chars from user input

**Scenario Type**: Negative
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: NFR-7
**Test Type(s)**: Unit
**Automation Level**: Automated
**Target Layer / Location**: `tests/unit/`
**Tags**: @backend

**Preconditions**:

- Sanitization is applied before intent/constraints are included in the LLM prompt.

**Steps**:

1. Provide `intent` and/or `constraints` containing control characters (e.g., newlines with control codes).
2. Build the prompt.

**Expected Outcome**:

- The prompt does not include control characters; sanitized text is used.

#### TC-AGENTGEN-009 - Request schema accepts preferred_skill_ids and passes through

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: DM-1, API-1, AC-DM1-1
**Test Type(s)**: Integration
**Automation Level**: Automated
**Target Layer / Location**: `tests/integration/`
**Tags**: @backend, @api

**Preconditions**:

- The request schema includes `preferred_skill_ids?: string[]`.

**Steps**:

1. Call `POST /api/agents/generate-draft` including `preferred_skill_ids` with 1–2 known skill IDs.
2. Ensure the request is accepted and processed.

**Expected Outcome**:

- HTTP 200.
- No validation error for `preferred_skill_ids`.
- The generation service receives the field (verified via a controllable mock/stub or observable trace content).

#### TC-AGENTGEN-010 - UI: family dropdown populated + selection sent as preferred_family

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-7, API-2, AC-F7-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend modal (Generate Agent)
**Tags**: @ui

**Preconditions**:

- Frontend is running and can call the backend.
- Backend returns at least one family from `GET /api/families`.

**Steps**:

1. Open the Generate Agent modal.
2. Verify a family dropdown is visible.
3. Select a family.
4. Click “Generate”.
5. Inspect the outbound request payload (browser devtools).

**Expected Outcome**:

- Dropdown options reflect the `/api/families` response.
- Selected family is sent as `preferred_family` in the request.

#### TC-AGENTGEN-011 - UI: skills multi-select populated + selected IDs sent as preferred_skill_ids

**Scenario Type**: Happy Path
**Impact Level**: Important
**Priority**: Medium
**Related IDs**: F-8, API-3, DM-1, AC-F8-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend modal (Generate Agent)
**Tags**: @ui

**Preconditions**:

- Frontend is running and can call the backend.
- Backend returns at least one skill from `GET /api/skills`.

**Steps**:

1. Open the Generate Agent modal.
2. Verify a skills multi-select is visible.
3. Select one or more skills.
4. Click “Generate”.
5. Inspect the outbound request payload (browser devtools).

**Expected Outcome**:

- Options reflect the `/api/skills` response.
- Selected skill IDs are sent as `preferred_skill_ids`.

#### TC-AGENTGEN-012 - UI: source badge copy + MCP rationale displayed per MCP

**Scenario Type**: Regression
**Impact Level**: Critical
**Priority**: High
**Related IDs**: F-5, F-9, F-10, AC-F5-1, AC-F9-1
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: Frontend modal (review step)
**Tags**: @ui

**Preconditions**:

- Two responses can be produced:
  - One with `source="llm"` and non-empty `mcp_rationale`.
  - One with `source="heuristic_template"`.

**Steps**:

1. Trigger generation resulting in `source="llm"`.
2. In the review step, verify the source badge copy.
3. For each MCP checkbox, verify the rationale text is displayed.
4. Trigger generation resulting in `source="heuristic_template"`.
5. Verify the fallback source badge copy.

**Expected Outcome**:

- For `source="llm"`, badge reads “AI-Powered”.
- For `source="heuristic_template"`, badge reads “Template (AI unavailable)”.
- MCP rationales are displayed for each MCP that has an entry in `mcp_rationale`.

#### TC-AGENTGEN-013 - Manual performance checks (LLM path ≤30s; fallback ≤500ms)

**Scenario Type**: Regression
**Impact Level**: Minor
**Priority**: Low
**Related IDs**: NFR-1, NFR-2
**Test Type(s)**: Manual
**Automation Level**: Manual
**Target Layer / Location**: End-to-end user flow
**Tags**: @perf

**Preconditions**:

- A local or representative environment where latency can be observed.

**Steps**:

1. Trigger generation with LLM enabled; measure elapsed time from request start to response received.
2. Trigger generation with LLM disabled/unreachable; measure elapsed time.

**Expected Outcome**:

- LLM path completes within 30 seconds at P95 for representative runs.
- Fallback path completes within 500 ms for representative runs.

## 6. Environments and Test Data

- **Backend automated tests**: use repo-standard pytest environment per `.ai/rules/testing-strategy.md`.
- Seed/fixtures need at minimum:
  - MCP catalog entries
  - Families
  - Skills
  - Existing agents (for “similar agents” context)
- **Trace writing tests**: set `ORKESTRA_DEBUG_AGENT_GENERATION_DIR` to an isolated temporary directory.
- **Frontend manual tests**: a running frontend connected to a backend instance with `/api/families` and `/api/skills` returning non-empty lists.

## 7. Automation Plan and Implementation Mapping

| TC-ID | Planned Automation | Target location (per strategy) |
|---|---|---|
| TC-AGENTGEN-001 | Automated | `tests/e2e/` (API E2E calling running backend over HTTP) |
| TC-AGENTGEN-002 | Automated | `tests/unit/` (prompt builder) |
| TC-AGENTGEN-003 | Automated | `tests/unit/` (LLM JSON parsing/validation helper) |
| TC-AGENTGEN-004 | Automated | `tests/unit/` (draft correction rules) |
| TC-AGENTGEN-005 | Automated | `tests/integration/` (endpoint + injected failing LLM) |
| TC-AGENTGEN-006 | Automated | `tests/integration/` (endpoint + unparseable JSON) |
| TC-AGENTGEN-007 | Automated | `tests/integration/` (trace dir + success/failure) |
| TC-AGENTGEN-008 | Automated | `tests/unit/` (sanitization) |
| TC-AGENTGEN-009 | Automated | `tests/integration/` (schema + endpoint) |
| TC-AGENTGEN-010 | Manual | Frontend (Generate Agent modal intent form) |
| TC-AGENTGEN-011 | Manual | Frontend (Generate Agent modal intent form) |
| TC-AGENTGEN-012 | Manual | Frontend (Generate Agent modal review step) |
| TC-AGENTGEN-013 | Manual | End-to-end measurement |

## 8. Risks, Assumptions, and Open Questions

**Risks**:

- API E2E harness availability: the repo strategy references `tests/e2e/` but may not yet have a standard way to start a test backend service for E2E.
- Trace file timing: asserting “within ≤ 1 s of response” can be flaky if trace writing is async; tests should be written to avoid timing fragility where possible.

**Assumptions (from spec)**:

- `GET /api/families` and `GET /api/skills` exist and are stable for frontend consumption.
- LLM calls follow the established orchestrator-builder pattern and can be mocked/injected in tests.

**Open Questions (carried from spec)**:

- OQ-1 Similar agents strategy (keyword overlap vs embeddings vs family filter) affects test data design for TC-AGENTGEN-002 and TC-AGENTGEN-001.
- OQ-4 Debug trace directory naming/structure: tests in TC-AGENTGEN-007 should follow the final decision.

## 9. Plan Revision Log

| Version | Date (UTC) | Author | Change |
|---:|---|---|---|
| 0.1 | 2026-04-28T21:06:46Z | mbensass | Initial test plan (Proposed) |

## 10. Test Execution Log

| Date (UTC) | Executor | Environment | TC-ID(s) | Result | Notes |
|---|---|---|---|---|---|
