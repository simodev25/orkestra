# Orkestra Mesh — Agent Reference

Full technical reference for agent definitions, lifecycle, factory, prompt composition, and governance.

---

## Agent definition fields

All fields from `AgentDefinition` (`app/models/registry.py`):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | str | required | Unique slug (e.g., `identity_resolution_agent`) |
| `name` | str | required | Display name |
| `family_id` | str (FK) | required | Must reference an active `FamilyDefinition` |
| `purpose` | str | required | One-sentence mission statement |
| `description` | str | null | Detailed description |
| `selection_hints` | dict | null | Selection criteria metadata (JSONB) |
| `allowed_mcps` | list | null | MCP server IDs the agent may use |
| `forbidden_effects` | list | null | Effect categories this agent is forbidden from triggering |
| `input_contract_ref` | str | null | Reference to input schema (prompt Layer 6) |
| `output_contract_ref` | str | null | Reference to output schema (prompt Layer 6) |
| `criticality` | str | `"medium"` | `"low"` \| `"medium"` \| `"high"` — affects Layer 7 |
| `cost_profile` | str | `"medium"` | `"low"` \| `"medium"` \| `"high"` |
| `limitations` | list | null | Known limitations injected in Layer 7 (JSONB) |
| `prompt_ref` | str | null | Reference to prompt template |
| `prompt_content` | text | null | Inline system prompt (Layer 4) |
| `skills_ref` | str | null | Reference to skills definition |
| `skills_content` | text | null | Resolved skill definitions (auto-generated from `skill_ids`) |
| `soul_content` | text | null | Agent persona/behavior (Layer 3, skipped if empty) |
| `llm_provider` | str | null | `"ollama"` or `"openai"` — falls back to platform default |
| `llm_model` | str | null | Model name — falls back to platform default |
| `allow_code_execution` | bool | `false` | Enables `execute_python_code` tool (Docker sandbox) |
| `allowed_builtin_tools` | list | null | AgentScope built-in tools |
| `last_test_status` | str | `"not_tested"` | `"not_tested"` \| `"passed"` \| `"failed"` |
| `last_validated_at` | datetime | null | Timestamp of last governance validation |
| `usage_count` | int | `0` | Number of invocations |
| `version` | str | `"1.0.0"` | Semantic version |
| `status` | str | `"draft"` | Lifecycle state |
| `owner` | str | null | Owner identifier |

---

## Agent lifecycle

State machine defined in `app/state_machines/agent_lifecycle_sm.py`. Promotion transitions:

```
draft → designed → tested → registered → active
                                              ↓          ↓
                                        deprecated    disabled
                                              ↓       ↓    ↓
                                           archived  active archived
```

Transitions allowed per state (confirmed by `app/state_machines/agent_lifecycle_sm.py`):

| From | To |
|------|----|
| `draft` | `designed` |
| `designed` | `tested` |
| `tested` | `registered` |
| `registered` | `active` |
| `active` | `deprecated` or `disabled` |
| `deprecated` | `archived` |
| `disabled` | `active` or `archived` |

**No programmatic gate conditions exist** on any transition beyond the allowed-transitions table. The `last_test_status` field is tracked by the Test Lab but is not checked by the state machine at transition time.

Lifecycle transitions are exposed via:

```
PATCH /api/agents/{id}/status
Body: { "status": "..." }
```

Invalid transitions return HTTP 409.

---

## Agent factory

`app/services/agent_factory.py` — `create_agentscope_agent(agent_def, db, tools_to_register, max_iters, fallback_model, fallback_formatter)`

Build steps:

1. Resolve LLM model: use `agent_def.llm_model` if set; otherwise use fallback model from config.
2. Create AgentScope `LLMResponseFormat`.
3. Build Toolkit: register each tool from `tools_to_register`.
4. If `allow_code_execution=True`: register the `execute_python_code` sandbox tool.
5. Register skill tools if `skills_content` is set.
6. Create `ReActAgent(name, sys_prompt, model, toolkit, max_iters)`.

`get_tools_for_agent(agent_def)` resolves MCP tools:

1. Read `agent_def.allowed_mcps` list.
2. For each MCP ID: call `obot_catalog_service.fetch_obot_server_by_id()` to get the endpoint URL.
3. Check `OrkestraMCPBinding.enabled_in_orkestra`.
4. Return list of tool configurations.

---

## 7-layer prompt composition

`app/services/prompt_builder.py` — `build_agent_prompt(db, agent, runtime_context)`:

| # | Section header | Source | Notes |
|---|----------------|--------|-------|
| 1 | FAMILY RULES | `family.default_system_rules` | Always included |
| 2 | SKILL RULES | Each skill: `behavior_templates` + `output_guidelines` | One block per skill; skipped if agent has no skills |
| 3 | SOUL | `agent.soul_content` | Skipped if empty |
| 4 | AGENT MISSION | `agent.name`, `purpose`, `description`, `prompt_content` | Always included |
| 5 | OUTPUT EXPECTATIONS | `family.default_output_expectations` | Always included |
| 6 | CONTRACTS | `agent.input_contract_ref` + `agent.output_contract_ref` | Skipped if both empty |
| 7 | RUNTIME CONTEXT | `criticality`, `forbidden_effects` (family ∪ agent), allowed tools, `limitations`, `runtime_context` | Always included |

Layer 7 forbidden effects = `set(family.default_forbidden_effects) ∪ set(agent.forbidden_effects)`.

---

## Code execution sandbox

When `allow_code_execution=True`, the `execute_python_code` tool is available to the agent.

- Code runs in a Docker container using `python:3.12-slim`.
- The API container mounts `/var/run/docker.sock`.
- Sandbox implementation: `app/services/sandbox_tool.py`.

---

## Versioning

Every mutation to an agent via `PATCH /api/agents/{id}` creates an `AgentDefinitionHistory` record.

History endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /api/agents/{id}/history` | List all recorded versions |
| `POST /api/agents/{id}/restore/{history_id}` | Restore a previous version |

The `version` field is a semantic version string managed manually by the API caller, defaulting to `"1.0.0"`.

---

## Governance

### Declared constraints

- `agent.forbidden_effects`: effect categories this agent should not trigger.
- `family.default_forbidden_effects`: inherited by all agents in the family.

### Enforcement mechanism

These constraints are injected as text in Layer 7 of the system prompt. The LLM is instructed to avoid the listed effects.

**No code-level enforcement exists at the API layer.** An LLM can ignore the constraint. Enforcement is entirely model-behavioral.

### Audit trail

`AuditEvent` records are written for agent creation, update, and status transitions. Stored in the `audit_events` table, readable via `GET /api/audit`.
