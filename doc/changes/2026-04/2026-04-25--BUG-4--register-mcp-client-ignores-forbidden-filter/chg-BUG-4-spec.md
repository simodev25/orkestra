---
change:
  ref: BUG-4
  type: fix
  status: Proposed
  slug: register-mcp-client-ignores-forbidden-filter
  title: "Pass filtered MCP tool names to register_mcp_client"
  owners: [mbensass]
  service: agent-factory
  labels: [security, mcp, forbidden-effects]
  version_impact: patch
---

# Summary

`create_agentscope_agent` filters MCP tools via `_enforce_forbidden_effects_on_mcp_tools()`, but `toolkit.register_mcp_client(...)` is called without `enable_funcs`, so AgentScope re-registers all server tools. This bypasses `forbidden_effects`.

# Goals

- Ensure the filtered MCP tool list is the one registered in AgentScope.
- Preserve existing behavior for agents without `forbidden_effects`.
- Avoid registration when filtering leaves zero tools.

# Acceptance Criteria

1. Given `forbidden_effects=["write"]` and MCP tools `[write_doc, list_docs]`, when agent creation registers the MCP client, then `enable_funcs` excludes `write_doc`.
2. Given the same setup, `enable_funcs` includes `list_docs`.
3. Given no `forbidden_effects`, `enable_funcs` includes all tools returned by MCP.
4. Given all tools filtered out, `register_mcp_client` is not called.
5. Implementation change is limited to passing `enable_funcs=[t.name for t in mcp_tools]` in `agent_factory.py`.
