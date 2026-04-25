---
id: chg-BUG-3-forbidden-effects-bypassed-outside-test-lab
status: Proposed
created: 2026-04-25T12:30:26Z
last_updated: 2026-04-25T12:30:26Z
owners:
  - mbensass
service: agent-factory
labels:
  - security
  - enforcement
  - agent-factory
  - forbidden-effects
links:
  change_spec: doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/chg-BUG-3-spec.md
summary: >-
  Fix BUG-3 by enforcing agent forbidden_effects unconditionally during agent construction,
  preserving Test Lab audit behavior (MCPInvocation + mcp.denied) when test_run_id+db exist,
  emitting WARNING logs otherwise, and removing dead guarded_mcp_executor code.
version_impact: patch
---

## Context and Goals

BUG-3: `forbidden_effects` enforcement is currently gated on `test_run_id` (Test Lab only), causing agents constructed in normal execution paths (subagent/pipeline/standalone) to bypass tool exclusion.

Goals (from spec):

- Enforce `agent_def.forbidden_effects` in all contexts (unconditional tool exclusion at construction time).
- Preserve existing Test Lab auditing when both `test_run_id` and `db` are available: persist `MCPInvocation` and emit `mcp.denied`.
- Outside Test Lab context: emit structured WARNING logs only (no DB persistence; avoid orphan records).
- Remove dead module `app/services/guarded_mcp_executor.py`.

Open questions (from spec):

- Are there any other callers that pass `test_run_id` besides Test Lab, and do they require full audit vs. log-only?
- Should WARNING logs be rate-limited/deduplicated to avoid flooding?

## Scope

### In Scope

- Update enforcement condition and branching logic in `app/services/agent_factory.py`.
- Ensure forbidden tools are excluded from `_allowed_tools` / toolkit registration in all contexts.
- Delete `app/services/guarded_mcp_executor.py` and ensure no references remain.
- Add regression tests per test plan to cover both paths and invariants.

### Out of Scope

- Changes to `effect_classifier.py` caching behavior.
- Runtime (post-construction) blocking of tool calls.
- Creating `MCPInvocation` records without a valid `test_run_id`.

### Constraints

- Do not create DB audit artifacts without `test_run_id`.
- Preserve Test Lab audit behavior exactly when `test_run_id` and `db` exist.
- Logging must be WARNING level for non-test-lab exclusions and include structured fields required by spec.

### Risks

- Behavioral change: agents previously relying on bypass will now lose forbidden tools in production.
- Potential log volume increase for agents frequently constructed with forbidden tools.

### Success Metrics

- Agents with non-empty `forbidden_effects` never register tools in forbidden effect categories regardless of `test_run_id`.
- Test Lab: denied tools produce `MCPInvocation` + `mcp.denied` event (no regression).
- Non-Test Lab: denied tools produce exactly one WARNING log per excluded tool and no `MCPInvocation`.
- `guarded_mcp_executor.py` absent and unreferenced.

## Phases

### Phase 1: Fix unconditional enforcement in `agent_factory.py`

**Goal**: Remove the Test Lab gate so forbidden effects are enforced in all execution contexts, while keeping audit behavior context-aware.

**Tasks**:

- [x] Locate the forbidden-effects enforcement block in `app/services/agent_factory.py` (~line 368 per spec appendix). (updated block near previous line ~368; evidence: `app/services/agent_factory.py`)
- [x] Change the enforcement condition to be unconditional on `agent_def.forbidden_effects`. (implemented helper `_enforce_forbidden_effects_on_mcp_tools`; evidence: `app/services/agent_factory.py`)
- [x] Split the prior inner behavior into two branches: (Test Lab audit path retained; non-test-lab warning-only path added)
  - Branch A (Test Lab): when `test_run_id` and `db` are present → preserve existing behavior (persist `MCPInvocation` + emit `mcp.denied`).
  - Branch B (non-Test Lab): otherwise → emit structured WARNING log only; do not persist.
- [x] Ensure tool exclusion is applied in both branches (tool never appears in `_allowed_tools` and is not registered in the toolkit). (denied tools excluded in helper return list)

**Acceptance Criteria**:

- Criterion: Tools matching forbidden effect categories are excluded from the constructed agent toolkit whenever `agent_def.forbidden_effects` is set (with or without `test_run_id`). — PASSED (helper enforces filtering unconditionally; validated by `test_forbidden_tool_excluded_without_run_id`)
- Criterion: In Test Lab context (`test_run_id` + `db`), existing `MCPInvocation` persistence and `mcp.denied` event emission remain unchanged. — PASSED (validated by `test_with_run_id_persists_denied_invocation_and_emits_event`)
- Criterion: Outside Test Lab, no `MCPInvocation` is created; a WARNING log is emitted once per excluded tool with required structured fields. — PASSED (validated by `test_warning_logged_without_run_id`; non-test-lab path does not persist without `test_run_id`)

**Files and modules**:

- `app/services/agent_factory.py`

**Exact code change (Phase 1 enforcement condition + branching skeleton)**:

```python
# BEFORE
if agent_def.forbidden_effects and test_run_id and db:
    ...

# AFTER (condition)
if agent_def.forbidden_effects:
    ...
    if test_run_id and db:
        # Branch A (Test Lab): preserve existing behavior
        # - persist MCPInvocation
        # - emit mcp.denied
        ...
    else:
        # Branch B (non-Test Lab): log WARNING only
        logger.warning(
            "mcp.denied (non-test-lab): tool excluded by forbidden_effects",
            extra={
                "agent_id": getattr(agent_def, "id", None),
                "tool_name": tool_name,
                "forbidden_effect": matched_effect,
                "context": "non_test_lab",
            },
        )
```

Notes:

- Keep the existing exclusion logic (do not add denied tools to `_allowed_tools` / toolkit) as the enforcement mechanism.
- Use the repo’s existing logger in this module (no new logging framework).

**Tests**:

- Covered by Phase 3 test cases TC-FORBIDDEN-001/002/004/005.

**Completion signal**: Changes implemented in `agent_factory.py` with unit/integration tests planned in Phase 3.

### Phase 2: Remove dead `guarded_mcp_executor.py`

**Goal**: Remove unused enforcement module to eliminate architectural confusion.

**Tasks**:

- [x] Delete `app/services/guarded_mcp_executor.py`. (deleted file; evidence: git diff)
- [x] Verify no code references/imports remain (per spec: none exist currently). (repo Python search: no `guarded_mcp_executor` matches)

**Acceptance Criteria**:

- Criterion: `app/services/guarded_mcp_executor.py` does not exist. — PASSED (validated by `test_guarded_mcp_executor_deleted`)
- Criterion: No imports/reference strings for `guarded_mcp_executor` remain. — PASSED (repo Python grep returned no matches)

**Files and modules**:

- `app/services/guarded_mcp_executor.py` (delete)

**Tests**:

- Covered by Phase 3 assertion `guarded_mcp_executor.py does not exist`.

**Completion signal**: File deleted; repository search shows no references.

### Phase 3: Add regression tests for BUG-3

**Goal**: Prevent recurrence of the bypass and preserve Test Lab audit behavior.

**Tasks**:

- [x] Create `tests/test_bug3_forbidden_effects_enforcement.py`. (new regression test file added)
- [x] Implement tests per test plan: (all 5 BUG-3 tests implemented and passing)
  - [x] Enforcement fires without `test_run_id` → tool excluded from toolkit. (`test_forbidden_tool_excluded_without_run_id`)
  - [x] With `test_run_id` + `db` → existing behavior preserved (MCPInvocation + `mcp.denied`). (`test_with_run_id_persists_denied_invocation_and_emits_event`)
  - [x] Agent without `forbidden_effects` → all tools registered normally. (`test_no_forbidden_effects_all_tools_registered`)
  - [x] WARNING log emitted in non-test-lab path. (`test_warning_logged_without_run_id`)
  - [x] `guarded_mcp_executor.py` does not exist. (`test_guarded_mcp_executor_deleted`)

**Acceptance Criteria**:

- Criterion: Tests map to spec ACs: AC-F1-1/2/3, AC-F2-1/2, AC-F3-1. — PASSED (direct mapping in test names above)
- Criterion: Tests are deterministic and do not rely on external services. — PASSED (unit tests use mocks/stubs only)

**Files and modules**:

- `tests/test_bug3_forbidden_effects_enforcement.py`

**Tests**:

- `pytest` (unit + integration as needed with in-memory SQLite fixtures already used by repo).

**Completion signal**: All new tests pass locally and cover both enforcement branches.

### Phase 4: Finalize, docs sync, and release hygiene

**Goal**: Ensure the change is ready to merge/release and reconciled with documentation.

**Tasks**:

- [x] Reconcile implementation against spec + test plan (no drift): confirm unconditional enforcement, branch-specific auditing, and dead-code removal. (completed via code + regression tests)
- [x] Version bump per repo conventions for `version_impact: patch` (only if this repo requires explicit version bump for patch fixes). (no explicit repo version/CHANGELOG bump convention found; no bump applied)

**Acceptance Criteria**:

- Criterion: Implementation matches spec acceptance criteria. — PASSED (Phase 1-3 criteria validated by tests + code inspection)
- Criterion: Any required patch version bump is applied following repo convention. — PASSED (not required by repository conventions discovered)

**Files and modules**:

- Version file(s) per repo convention (if applicable).

**Tests**:

- Run targeted test file and any relevant suite subset per repo conventions.

**Completion signal**: Ready for review; versioning addressed if required.

### Phase 5: Code Review (Analysis)

**Goal**: Validate correctness, security intent, and non-regression.

**Tasks**:

- [x] Self-review diff against spec ACs and test plan TCs. (Skipped formal review phase per user instruction: "No review needed"; reconciliation performed in Phase 4)
- [x] Ensure non-test-lab logging is WARNING and includes required fields. (validated by `test_warning_logged_without_run_id`)
- [x] Ensure Test Lab path remains unchanged (no behavior regression). (validated by `test_with_run_id_persists_denied_invocation_and_emits_event`)

**Acceptance Criteria**:

- Criterion: Reviewer can trace enforcement and auditing behavior clearly in `agent_factory.py`. — PASSED (logic centralized in `_enforce_forbidden_effects_on_mcp_tools` and invoked in MCP registration path)

**Completion signal**: Review feedback ready (or none).

### Phase 6: Post-Code Review Fixes (conditional)

**Goal**: Address review feedback without changing scope.

**Tasks**:

- [x] Apply requested changes. (N/A — no review feedback requested)
- [x] Re-run tests impacted by changes. (targeted BUG-3 regression suite executed)

**Acceptance Criteria**:

- Criterion: All acceptance criteria still met; no spec drift. — PASSED (no post-review deltas)

**Completion signal**: Review threads resolved.

### Phase 7: Finalize and Release

**Goal**: Land BUG-3 safely with required metadata.

**Tasks**:

- [x] Ensure final patch version bump is done (if required by repo). (not required per repo conventions discovered)
- [x] Spec reconciliation: confirm spec/test plan references are correct; ensure this plan remains accurate. (completed)
- [x] Commit changes with message referencing BUG-3. (evidence: this BUG-3 commit on branch `fix/BUG-3/forbidden-effects-bypassed-outside-test-lab`)

**Acceptance Criteria**:

- Must: Single commit (or repo-acceptable commit set) includes code + tests + deletion.
- Must: Commit message references `BUG-3`.

**Completion signal**: Changes committed on branch `fix/BUG-3/forbidden-effects-bypassed-outside-test-lab`.

## Test Scenarios

Primary scenarios (from `chg-BUG-3-test-plan.md`):

- TC-FORBIDDEN-001: Enforce forbidden effects without `test_run_id` (regression).
- TC-FORBIDDEN-002: Preserve Test Lab audit path (tool excluded + MCPInvocation + `mcp.denied`).
- TC-FORBIDDEN-003: Agents without `forbidden_effects` unchanged.
- TC-FORBIDDEN-004: Non-test-lab enforcement emits exactly one WARNING per excluded tool.
- TC-FORBIDDEN-005: Non-test-lab enforcement creates no MCPInvocation records.
- TC-FORBIDDEN-006: `guarded_mcp_executor.py` removed and unreferenced.

## Artifacts and Links

- Change folder: `doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/`
- Spec: `doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/chg-BUG-3-spec.md`
- Test plan: `doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/chg-BUG-3-test-plan.md`
- Implementation plan (this file): `doc/changes/2026-04/2026-04-25--BUG-3--forbidden-effects-bypassed-outside-test-lab/chg-BUG-3-plan.md`

## Plan Revision Log

| Date (UTC) | Author | Change |
|---|---|---|
| 2026-04-25 | mbensass | Initial implementation plan for BUG-3 (Proposed) |
| 2026-04-25 | codex | Execution updates: phases 1-6 marked complete with evidence; final commit pending |

## Execution Log

| Date (UTC) | Executor | Phase | Result | Notes |
|---|---|---|---|---|
| 2026-04-25 | codex | Phase 1 | PASS | Unconditional enforcement implemented in `agent_factory.py`; audit path retained |
| 2026-04-25 | codex | Phase 2 | PASS | `app/services/guarded_mcp_executor.py` deleted; references removed from Python tests/code |
| 2026-04-25 | codex | Phase 3 | PASS | Added `tests/test_bug3_forbidden_effects_enforcement.py` with 5 deterministic regression tests |
| 2026-04-25 | codex | Phase 4 | PASS | Ran `python3 -m pytest tests/test_bug3_forbidden_effects_enforcement.py -v -q --no-header` (5 passed) |
| 2026-04-25 | codex | Phase 5-6 | PASS | User requested no review; no remediation feedback |
| 2026-04-25 | codex | Phase 7 | PASS | Final BUG-3 commit created on target branch |
