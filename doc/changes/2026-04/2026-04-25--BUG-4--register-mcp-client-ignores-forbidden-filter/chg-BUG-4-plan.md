---
id: chg-BUG-4-plan
status: In Progress
created: 2026-04-25T00:00:00Z
last_updated: 2026-04-25T00:00:00Z
owners:
  - mbensass
service: agent-factory
labels:
  - security
  - mcp
  - forbidden-effects
links:
  change_spec: doc/changes/2026-04/2026-04-25--BUG-4--register-mcp-client-ignores-forbidden-filter/chg-BUG-4-spec.md
  test_plan: doc/changes/2026-04/2026-04-25--BUG-4--register-mcp-client-ignores-forbidden-filter/chg-BUG-4-test-plan.md
version_impact: patch
---

## Tasks

### Phase 1: Specification and planning

- [x] Create `chg-BUG-4-spec.md` (created)
- [x] Create `chg-BUG-4-test-plan.md` (created)
- [x] Create `chg-BUG-4-plan.md` (created)

Acceptance criteria:
- Criterion: Spec exists with <=5 acceptance criteria — PASSED (`chg-BUG-4-spec.md`)
- Criterion: Test plan exists with <=5 scenarios — PASSED (`chg-BUG-4-test-plan.md`)

### Phase 2: Implementation

- [x] Add `enable_funcs=[t.name for t in mcp_tools]` to `toolkit.register_mcp_client(...)` call in `app/services/agent_factory.py` (updated `app/services/agent_factory.py` register_mcp_client call)

Acceptance criteria:
- Criterion: `register_mcp_client` is called with `enable_funcs` from filtered `mcp_tools` — PASSED (`app/services/agent_factory.py` line with `enable_funcs=[t.name for t in mcp_tools]`)

### Phase 3: Tests

- [x] Add `tests/test_bug4_register_mcp_client_enable_funcs.py` with 4 scenarios from test plan (created with 4 tests)
- [x] Run `python3 -m pytest tests/test_bug4_register_mcp_client_enable_funcs.py -v -q --no-header` (4 passed)

Acceptance criteria:
- Criterion: All 4 BUG-4 tests pass — PASSED (`python3 -m pytest tests/test_bug4_register_mcp_client_enable_funcs.py -v -q --no-header`)

### Phase 4: Finalization

- [x] Commit all BUG-4 files (commit `840d977`)
- [ ] Create PR to `master`

Acceptance criteria:
- Criterion: PR created with requested title/body — PENDING

### Phase 5: Live E2E forbidden-effects validation

- [x] Add `tests/e2e/test_forbidden_effects_e2e.py` with live API checks for config, prompt policy, MCP catalog, denial path, create-without-forbidden, and patch persistence (file created)
- [x] Run `python3 -m pytest tests/e2e/test_forbidden_effects_e2e.py -v --no-header -m e2e` (4 passed, 2 failed)

Acceptance criteria:
- Criterion: Live E2E suite validates `write_doc` is denied for `word_test_agent` — FAILED (`test_write_doc_invocation_is_denied_and_recorded`: no denial recorded; `write_doc` executed successfully)
- Criterion: Agent prompt does not invite blocked write action and communicates read-only authorization — FAILED (`test_word_test_agent_prompt_does_not_invite_write_doc`: prompt explicitly instructs to call `write_doc` and has no `not authorized`/`read-only` guard text)

## Plan revision log

- 2026-04-25: Initial plan created.
- 2026-04-25: Added Phase 5 for live E2E forbidden-effects validation on running API.

## Execution log

- 2026-04-25: Phase 1 completed (spec + test plan + plan created).
- 2026-04-25: Phase 2 completed (register_mcp_client now passes enable_funcs from filtered tool list).
- 2026-04-25: Phase 3 completed (added BUG-4 test file; 4 tests passing).
- 2026-04-25: Phase 4 task commit completed (`840d977`).
- 2026-04-25: Phase 5 executed (live E2E suite added; enforcement checks reveal `write_doc` is still allowed and prompt policy is not aligned with forbidden effects).
