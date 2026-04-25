---
id: chg-BUG-2-word-test-agent-write-bypass
status: Proposed
created: 2026-04-24T16:08:43Z
last_updated: 2026-04-24T16:08:43Z
owners:
  - mbensass
service: "agent-runtime / word-mcp"
labels:
  - security
  - agent-policy
  - bug
links:
  change_spec: doc/changes/2026-04/2026-04-24--BUG-2--word-test-agent-write-bypass/chg-BUG-2-spec.md
summary: >-
  Correct a policy misconfiguration in word_test_agent that permitted write_doc via missing
  forbidden_effects ("write") and related prompt/routing/metadata defects; add automated
  regression coverage.
version_impact: patch
---

## Context and Goals

This change fixes a security-relevant policy misconfiguration where the read-only `word_test_agent` could invoke the Word MCP `write_doc` tool because the agent definition omitted the `"write"` effect from `forbidden_effects` and included conflicting prompt/routing content.

**Goals (from spec)**:

- Ensure `write_doc` invocations by `word_test_agent` are always denied by `guarded_mcp_executor`.
- Align agent prompt, routing keywords, and metadata with read-only intent.
- Add automated regression coverage for the acceptance criteria.

**Open questions**:

- OQ-1 (spec): confirm the executor’s effect mapping classifies `write_doc` as `"write"` (validated by TC-WORDTEST-001).
- NFR-2 (test plan): identify the canonical read tool(s) used by `word_test_agent` for non-regression coverage (TC-WORDTEST-008 is deferred in the test plan).

## Scope

### In Scope

- Agent definition fix already applied in `scripts/create_word_test_agent.py`.
- Add automated tests per test plan TC-WORDTEST-001 through TC-WORDTEST-006 in `tests/test_word_test_agent_policy.py`.
- Commit the changes.

### Out of Scope

- Any changes to `guarded_mcp_executor` logic (per spec).
- Changes to other agents or the Word MCP server.
- Automating TC-WORDTEST-007 / NFR-1 / NFR-2 if a deterministic harness/read-tool set is not available yet (remain manual/TODO per test plan).

### Constraints

- Tests must not call real MCP/LLM services; use mocks and static/config assertions.
- Plan should prioritize remaining work (tests) since the fix is already implemented.

### Risks

- Effect classification API/location may differ from what the test plan expects; adjust test imports/targets to match repo structure.
- Agent definition source of truth for tests must match runtime (ensure tests load the same definition produced by `scripts/create_word_test_agent.py`).

### Success Metrics

- TC-WORDTEST-001..006 pass in CI (automated regression coverage).
- At least one automated test asserts `write_doc` is denied for `word_test_agent` (AC-NFR3-1).

## Phases

### Phase 1: Policy fix (already applied)

**Goal**: Ensure `word_test_agent` definition cannot perform write operations.

**Tasks**:

- [x] Add `"write"` to `forbidden_effects` in `scripts/create_word_test_agent.py`.
- [x] Update prompt rule 4 to explicitly prohibit `write_doc`.
- [x] Update `purpose` and `description` to read-only scope.
- [x] Remove `"write_doc"` from `routing_keywords`.

**Acceptance Criteria**:

- Must: Spec AC-F1-1 / AC-F2-1 / AC-F3-1 / AC-F4-1 satisfied by agent definition content.

**Files and modules**:

- `scripts/create_word_test_agent.py`

**Tests**:

- Covered by Phase 2 tests.

**Completion signal**: Fix present on branch (no further code changes required for this phase).

### Phase 2: Automated regression tests (remaining work)

**Goal**: Add automated tests covering TC-WORDTEST-001..TC-WORDTEST-006 to prevent regressions.

**Tasks**:

- [x] Create `tests/test_word_test_agent_policy.py`. (added `tests/test_word_test_agent_policy.py`)
- [x] Implement TC-WORDTEST-001: effect classification maps `write_doc` → `["write"]`. (`test_tc_wordtest_001_heuristic_maps_write_doc_to_write`)
- [x] Implement TC-WORDTEST-002: `guarded_mcp_executor` denies `write_doc` when agent forbids `"write"` (assert `MCPInvocation.status == "denied"`; ensure MCP tool is not executed). (`test_tc_wordtest_002_executor_denies_write_doc_for_write_forbidden_agent`, `invoke_mcp` mocked/not called)
- [x] Implement TC-WORDTEST-003: `word_test_agent.forbidden_effects` contains `"write"`. (`test_tc_wordtest_003_agent_forbidden_effects_contains_write`)
- [x] Implement TC-WORDTEST-004: prompt content explicitly prohibits `write_doc` and does not invite it. (`test_tc_wordtest_004_prompt_prohibits_write_doc`)
- [x] Implement TC-WORDTEST-005: `routing_keywords` excludes `"write_doc"`. (`test_tc_wordtest_005_routing_keywords_excludes_write_doc`)
- [x] Implement TC-WORDTEST-006: `purpose`/`description` communicate read-only scope with no write capability claims. (`test_tc_wordtest_006_purpose_and_description_are_read_only`)

**Acceptance Criteria**:

- Must: TC-WORDTEST-001..006 pass locally via `pytest`. — PASSED (`python3 -m pytest tests/test_word_test_agent_policy.py -v --asyncio-mode=auto`, 6 passed)
- Must: Covers spec AC-F1-1, AC-F1-2, AC-F2-1, AC-F3-1, AC-F4-1, and AC-NFR3-1. — PASSED (TC-WORDTEST-001..006 implemented in `tests/test_word_test_agent_policy.py`)

**Files and modules**:

- `tests/test_word_test_agent_policy.py`

**Tests**:

- `pytest tests/test_word_test_agent_policy.py`

**Completion signal**: All automated tests green; coverage mapping in test plan satisfied for TC-WORDTEST-001..006.

### Phase 3: Finalize and Release

**Goal**: Land the change safely with correct version impact handling.

**Tasks**:

- [x] Reconcile with spec and test plan (ensure acceptance criteria are met and referenced tests exist). (validated AC-F1-1/AC-F1-2/AC-F2-1/AC-F3-1/AC-F4-1/AC-NFR3-1 via TC-WORDTEST-001..006)
- [x] Apply version bump if repo conventions require explicit bump for `version_impact: patch`. (no repo CHANGELOG/version-bump convention file found; no bump applied)
- [x] Commit all changes. (commit `9762144`: `test(BUG-2): add word_test_agent write bypass regression tests`)

**Acceptance Criteria**:

- Must: Git history contains a commit for BUG-2 work; tests pass. — PASSED (commit `9762144`; tests PASSED: `python3 -m pytest tests/test_word_test_agent_policy.py -v --asyncio-mode=auto`)
- Should: Spec/test plan links remain accurate. — PASSED (links unchanged and valid)

**Files and modules**:

- (As required by repo versioning conventions)

**Tests**:

- `pytest`

**Completion signal**: Commit created and working tree clean.

## Test Scenarios

Automated (required for this work item):

- TC-WORDTEST-001
- TC-WORDTEST-002
- TC-WORDTEST-003
- TC-WORDTEST-004
- TC-WORDTEST-005
- TC-WORDTEST-006

Manual / Deferred (per test plan; not required for this plan’s remaining work):

- TC-WORDTEST-007 (structured JSON error response)
- TC-WORDTEST-008 (read operations non-regression)
- TC-WORDTEST-009 (deny-path latency spot-check)

## Artifacts and Links

- Change spec: `doc/changes/2026-04/2026-04-24--BUG-2--word-test-agent-write-bypass/chg-BUG-2-spec.md`
- Test plan: `doc/changes/2026-04/2026-04-24--BUG-2--word-test-agent-write-bypass/chg-BUG-2-test-plan.md`
- Implementation plan (this file): `doc/changes/2026-04/2026-04-24--BUG-2--word-test-agent-write-bypass/chg-BUG-2-plan.md`

## Plan Revision Log

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-04-24 | mbensass | Initial implementation plan for BUG-2 (focus: automated tests) |

## Execution Log

| Date (UTC) | Executor | Branch | Notes |
|---|---|---|
| 2026-04-24 | @plan-writer | fix/BUG-2/word-test-agent-write-bypass | Plan created; fix marked done; tests & commit remain |
| 2026-04-24 | @coder | fix/BUG-2/word-test-agent-write-bypass | Phase 2 executed: added TC-WORDTEST-001..006 in `tests/test_word_test_agent_policy.py`; targeted pytest run passed (6/6). |
| 2026-04-24 | @committer | fix/BUG-2/word-test-agent-write-bypass | Phase 3 commit completed (`9762144`) after reconciliation/version-bump check. |
