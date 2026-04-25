---
id: chg-BUG-4-test-plan
status: Proposed
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
version_impact: patch
---

# Test Plan — BUG-4

## Scope

Validate that MCP registration honors the filtered tool set by passing `enable_funcs` derived from `_enforce_forbidden_effects_on_mcp_tools()` output.

## Scenarios

1. `test_enable_funcs_excludes_forbidden_tool`
   - Input tools: `write_doc`, `list_docs`
   - `forbidden_effects=["write"]`
   - Expect: `enable_funcs` does not contain `write_doc`.

2. `test_enable_funcs_contains_allowed_tool`
   - Same setup
   - Expect: `enable_funcs` contains `list_docs`.

3. `test_no_forbidden_effects_all_tools_in_enable_funcs`
   - `forbidden_effects=None`
   - Expect: all MCP tools are present in `enable_funcs`.

4. `test_empty_after_filter_no_registration`
   - All tools filtered out
   - Expect: `register_mcp_client` is not called.

## Execution Command

`python3 -m pytest tests/test_bug4_register_mcp_client_enable_funcs.py -v -q --no-header`
