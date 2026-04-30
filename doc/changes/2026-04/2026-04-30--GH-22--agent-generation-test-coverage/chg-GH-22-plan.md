# Implementation Plan — GH-22: Agent Generation Test Coverage

## Change Reference
- **workItemRef**: GH-22
- **Branch**: `test/GH-22/agent-generation-test-coverage`
- **Spec**: N/A (test-only change)

## Phase 1: Unit tests — service layer

### Files
- `tests/services/test_agent_generation_service.py` (modify)

### Tasks
- [x] T1.1: Add test `test_build_generation_prompt_handles_datetime_in_skills` — pass skills with `datetime` objects in `created_at`/`updated_at`, verify no exception (AC-2) (added in `tests/services/test_agent_generation_service.py`, pytest PASS: `test_build_generation_prompt_handles_datetime_in_skills`)
- [x] T1.2: Add test `test_normalize_llm_draft_with_zero_families` — pass empty families list in context, verify no crash and draft retains a family_id (AC-5) (added in `tests/services/test_agent_generation_service.py`, pytest PASS: `test_normalize_llm_draft_with_zero_families`)
- [x] T1.3: Add test `test_call_llm_handles_async_generator_response` — mock `get_chat_model` to return a model that yields an async generator, verify `_call_llm` collects chunks into a string (AC-1) (added in `tests/services/test_agent_generation_service.py`, pytest PASS: `test_call_llm_handles_async_generator_response`)
- [x] T1.4: Run `python3 -m pytest tests/services/test_agent_generation_service.py -x -q` — all pass (evidence: `8 passed`)

### Commit
```
test(agent-generation): add unit tests for datetime, empty families, and streaming (GH-22)
```

## Phase 2: E2E tests — realistic data

### Files
- `tests/e2e/test_generate_agent_draft_flow.py` (new)

### Tasks
- [x] T2.1: Add test `test_generate_draft_without_heuristic_default_families` — seed family "compliance" (not "analyst"), call generate-draft, verify draft family_id is valid (AC-3) (added in `tests/e2e/test_generate_agent_draft_flow.py`, pytest PASS)
- [x] T2.2: Add test `test_generate_draft_then_save_succeeds` — call generate-draft, then save-generated-draft with returned draft, assert 201 (AC-4) (added in `tests/e2e/test_generate_agent_draft_flow.py`, seeds required skills, pytest PASS)
- [x] T2.3: Add test `test_fallback_heuristic_normalizes_family_to_existing` — monkeypatch `_call_llm` to raise, seed family "compliance", call generate-draft, verify source="heuristic_template" and family_id matches existing DB family (AC-6) (added in `tests/e2e/test_generate_agent_draft_flow.py`, pytest PASS)
- [x] T2.4: Run `python3 -m pytest tests/e2e/test_generate_agent_draft_flow.py -x -q` — all pass (evidence: `3 passed`)

### Commit
```
test(agent-generation): add E2E tests with realistic data for draft generation (GH-22)
```

## Phase 3: Verification

### Tasks
- [ ] T3.1: Run full test suite `python3 -m pytest tests/services/test_agent_generation_service.py tests/e2e/test_generate_agent_draft_flow.py tests/test_api_agent_registry_product.py -x -q` — all pass
- [ ] T3.2: Run `python3 -m ruff check tests/` — no lint errors

## Execution Log

| Phase | Status | Evidence |
|-------|--------|----------|
| 1     | pending | — |
| 2     | pending | — |
| 3     | pending | — |
