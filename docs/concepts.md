# Orkestra Mesh — Core Concepts

This document defines each concept precisely, grounded in actual ORM models and code.

---

## Agent

An `AgentDefinition` record in the PostgreSQL database (`app/models/registry.py`). It is a blueprint, not a running process.

Key fields:

| Field | Description |
|-------|-------------|
| `id` | Unique slug (e.g., `identity_resolution_agent`) |
| `name` | Display name |
| `family_id` | FK to `FamilyDefinition` — required, must be active |
| `purpose` | One-sentence mission statement |
| `description` | Detailed description |
| `allowed_mcps` | JSONB list of MCP server IDs the agent may use |
| `forbidden_effects` | JSONB list of effect categories the agent must not trigger |
| `prompt_content` | Inline system prompt text (Layer 4) |
| `skills_content` | JSONB resolved skill definitions |
| `soul_content` | Agent persona/behavior (Layer 3) |
| `llm_provider` | `"ollama"` or `"openai"` — falls back to platform default |
| `llm_model` | Model name — falls back to platform default |
| `status` | Lifecycle state (see Lifecycle State) |
| `version` | Semantic version string |

When invoked, an in-memory AgentScope `ReActAgent` is created from the definition by `app/services/agent_factory.py`. The `ReActAgent` is not persisted and is destroyed after the run.

---

## Family

A `FamilyDefinition` record (`app/models/family.py`). Groups agents by operational context.

Contributions to agent behavior:

| Field | Injected as |
|-------|-------------|
| `default_system_rules` | Layer 1 of the system prompt — always included |
| `default_forbidden_effects` | Merged with `agent.forbidden_effects` in Layer 7 |
| `default_output_expectations` | Layer 5 — always included |

Every agent must belong to exactly one active family. `family_id` is required, and the referenced family must be active at agent creation time.

---

## Skill

A `SkillDefinition` reusable capability block (`app/models/skill.py`).

Key fields:

| Field | Description |
|-------|-------------|
| `behavior_templates` | Behavioral directives injected into prompt Layer 2 |
| `output_guidelines` | Output quality rules injected alongside behavior templates |
| `allowed_families` | Families whose agents may use this skill |

A skill can only be assigned to agents whose family appears in the skill's `allowed_families` list. This is validated at agent creation and update time.

Skills are loaded from `app/config/skills.seed.json` into an in-memory registry at startup. **Skills are NOT stored in the database.**

---

## MCP (Model Context Protocol)

A tool server registered in Orkestra as an `MCPDefinition`, or sourced from the Obot catalog as an `OrkestraMCPBinding`. MCP servers run inside Obot, not locally.

Agents declare which MCPs they may use via `allowed_mcps`. The governance overlay (`OrkestraMCPBinding.enabled_in_orkestra`) can disable a tool for all agents regardless of what `allowed_mcps` declares.

---

## Test Scenario

A `TestScenario` record (`app/models/test_lab.py`). Defines a reproducible test case.

| Field | Description |
|-------|-------------|
| `input_prompt` | Text sent to the agent under test |
| `assertions` | Structured expected-behavior declarations |
| `tags` | Arbitrary labels for filtering |
| `allowed_tools` | Tool restriction list (nullable = no restriction) |
| `timeout_seconds` | Execution time limit |
| `max_iterations` | Maximum ReAct loop iterations |

Running a scenario creates a `TestRun`.

---

## Test Run

A `TestRun` record representing one execution of a `TestScenario`.

| Field | Values / Description |
|-------|----------------------|
| `status` | `pending` \| `running` \| `completed` \| `failed` \| `timeout` |
| `verdict` | `passed` \| `failed` \| `unknown` |
| `score` | 0.0–100.0 assigned by `JudgeSubAgent` |
| `assertion_results` | Per-assertion pass/fail breakdown |
| `final_output` | Last agent message |
| `duration_ms` | Wall-clock execution time |

Events are streamed in real time via SSE.

---

## Approval

An `ApprovalRequest` record created when an agent action requires human sign-off.

State progression: `pending` → `approved` | `rejected`

Resolved by a human via:
- `POST /api/approvals/{id}/approve`
- `POST /api/approvals/{id}/reject`

**Important:** Approval requests are not automatically triggered during agent execution in the current implementation — they must be manually created and managed.

---

## Forbidden Effects

A list of effect category strings (e.g., `"external_write"`, `"financial_transaction"`) declared on:
- `agent.forbidden_effects` — agent-level
- `family.default_forbidden_effects` — family-level, inherited by all agents in the family

At runtime, the union of both lists is injected into the agent's system prompt as Layer 7. The LLM is instructed to avoid these effects.

**The API layer does not block calls based on this list.** Enforcement is purely model-behavioral — the LLM reads the constraint and may or may not comply.

---

## Lifecycle State

The current stage of an agent in the development pipeline. Controlled by `app/state_machines/agent_lifecycle_sm.py`.

```
draft → designed → tested → registered → active
                                            ↓          ↓
                                       deprecated   disabled
                                            ↓          ↓
                                         archived   archived
```

Allowed transitions:

| From | To |
|------|----|
| `draft` | `designed` |
| `designed` | `tested` |
| `tested` | `registered` |
| `registered` | `active` |
| `active` | `deprecated` or `disabled` |
| `deprecated` or `disabled` | `archived` |

Transitions are validated — you cannot jump directly from `draft` to `active`. Gate condition for `tested → registered`: `last_test_status` must be `"passed"`.

---

## OrchestratorAgent (Test Lab)

The LLM agent that coordinates test execution in the Test Lab. A `ReActAgent` with `max_iters=12` and a Toolkit of 8 tools.

Not to be confused with the agent under test (the TargetAgent). Configured via `GET /api/test-lab/config` and `PUT /api/test-lab/config`.
