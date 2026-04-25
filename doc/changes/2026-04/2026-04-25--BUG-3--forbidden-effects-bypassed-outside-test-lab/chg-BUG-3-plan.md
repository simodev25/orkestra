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

- [ ] Locate the forbidden-effects enforcement block in `app/services/agent_factory.py` (~line 368 per spec appendix).
- [ ] Change the enforcement condition to be unconditional on `agent_def.forbidden_effects`.
- [ ] Split the prior inner behavior into two branches:
  - Branch A (Test Lab): when `test_run_id` and `db` are present → preserve existing behavior (persist `MCPInvocation` + emit `mcp.denied`).
  - Branch B (non-Test Lab): otherwise → emit structured WARNING log only; do not persist.
- [ ] Ensure tool exclusion is applied in both branches (tool never appears in `_allowed_tools` and is not registered in the toolkit).

**Acceptance Criteria**:

- Must: Tools matching forbidden effect categories are excluded from the constructed agent toolkit whenever `agent_def.forbidden_effects` is set (with or without `test_run_id`).
- Must: In Test Lab context (`test_run_id` + `db`), existing `MCPInvocation` persistence and `mcp.denied` event emission remain unchanged.
- Must: Outside Test Lab, no `MCPInvocation` is created; a WARNING log is emitted once per excluded tool with required structured fields.

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

- [ ] Delete `app/services/guarded_mcp_executor.py`.
- [ ] Verify no code references/imports remain (per spec: none exist currently).

**Acceptance Criteria**:

- Must: `app/services/guarded_mcp_executor.py` does not exist.
- Must: No imports/reference strings for `guarded_mcp_executor` remain.

**Files and modules**:

- `app/services/guarded_mcp_executor.py` (delete)

**Tests**:

- Covered by Phase 3 assertion `guarded_mcp_executor.py does not exist`.

**Completion signal**: File deleted; repository search shows no references.

### Phase 3: Add regression tests for BUG-3

**Goal**: Prevent recurrence of the bypass and preserve Test Lab audit behavior.

**Tasks**:

- [ ] Create `tests/test_bug3_forbidden_effects_enforcement.py`.
- [ ] Implement tests per test plan:
  - [ ] Enforcement fires without `test_run_id` → tool excluded from toolkit.
  - [ ] With `test_run_id` + `db` → existing behavior preserved (MCPInvocation + `mcp.denied`).
  - [ ] Agent without `forbidden_effects` → all tools registered normally.
  - [ ] WARNING log emitted in non-test-lab path.
  - [ ] `guarded_mcp_executor.py` does not exist.

**Acceptance Criteria**:

- Must: Tests map to spec ACs: AC-F1-1/2/3, AC-F2-1/2, AC-F3-1.
- Must: Tests are deterministic and do not rely on external services.

**Files and modules**:

- `tests/test_bug3_forbidden_effects_enforcement.py`

**Tests**:

- `pytest` (unit + integration as needed with in-memory SQLite fixtures already used by repo).

**Completion signal**: All new tests pass locally and cover both enforcement branches.

### Phase 4: Finalize, docs sync, and release hygiene

**Goal**: Ensure the change is ready to merge/release and reconciled with documentation.

**Tasks**:

- [ ] Reconcile implementation against spec + test plan (no drift): confirm unconditional enforcement, branch-specific auditing, and dead-code removal.
- [ ] Version bump per repo conventions for `version_impact: patch` (only if this repo requires explicit version bump for patch fixes).

**Acceptance Criteria**:

- Must: Implementation matches spec acceptance criteria.
- Must: Any required patch version bump is applied following repo convention.

**Files and modules**:

- Version file(s) per repo convention (if applicable).

**Tests**:

- Run targeted test file and any relevant suite subset per repo conventions.

**Completion signal**: Ready for review; versioning addressed if required.

### Phase 5: Code Review (Analysis)

**Goal**: Validate correctness, security intent, and non-regression.

**Tasks**:

- [ ] Self-review diff against spec ACs and test plan TCs.
- [ ] Ensure non-test-lab logging is WARNING and includes required fields.
- [ ] Ensure Test Lab path remains unchanged (no behavior regression).

**Acceptance Criteria**:

- Must: Reviewer can trace enforcement and auditing behavior clearly in `agent_factory.py`.

**Completion signal**: Review feedback ready (or none).

### Phase 6: Post-Code Review Fixes (conditional)

**Goal**: Address review feedback without changing scope.

**Tasks**:

- [ ] Apply requested changes.
- [ ] Re-run tests impacted by changes.

**Acceptance Criteria**:

- Must: All acceptance criteria still met; no spec drift.

**Completion signal**: Review threads resolved.

### Phase 7: Finalize and Release

**Goal**: Land BUG-3 safely with required metadata.

**Tasks**:

- [ ] Ensure final patch version bump is done (if required by repo).
- [ ] Spec reconciliation: confirm spec/test plan references are correct; ensure this plan remains accurate.
- [ ] Commit changes with message referencing BUG-3.

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

## Execution Log

| Date (UTC) | Executor | Phase | Result | Notes |
|---|---|---|---|---|
| (not started) |  |  |  |  |
