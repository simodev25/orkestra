# Orkestra Mesh — Architecture

## Overview

Orkestra Mesh is a platform for defining, governing, and testing AI agents. It wraps the full agent lifecycle: from definition and versioning, through governed deployment and MCP tool binding, to automated test execution with LLM evaluation.

The system is composed of eleven backend subsystems, a Next.js frontend, and an async task queue. All subsystems communicate through a shared PostgreSQL database; no direct inter-service calls exist except for the Obot integration.

---

## Subsystems

| Subsystem | Responsibility | Key files |
|-----------|---------------|-----------|
| Agent Registry | CRUD, versioning, lifecycle state machine | `app/services/agent_registry_service.py`, `app/models/registry.py`, `app/state_machines/agent_lifecycle_sm.py` |
| Agent Factory | Creates live ReActAgent from an AgentDefinition | `app/services/agent_factory.py` |
| Families / Skills | Reusable prompt blocks; seeded from JSON at startup | `app/services/seed_service.py`, `app/config/families.seed.json`, `app/config/skills.seed.json` |
| MCP Integration | Obot catalog sync + local governance overlay | `app/services/obot_catalog_service.py`, `app/services/mcp_registry_service.py` |
| Test Lab | Scenario execution and LLM-based evaluation | `app/services/test_lab/` (16 files), `app/tasks/test_lab.py` |
| Governance | Approval workflows, audit trail, forbidden-effect declarations | `app/services/approval_service.py`, `app/services/audit_service.py`, `app/state_machines/` |
| Prompt Builder | Assembles the 7-layer system prompt | `app/services/prompt_builder.py` |
| Secrets | Fernet-encrypted secrets stored in the database | `app/services/secret_service.py`, `app/models/secret.py` |
| API Layer | FastAPI, 19 routers, rate limiting, auth | `app/main.py`, `app/api/routes/` |
| Async Queue | Celery + Redis; one registered task type | `app/celery_app.py`, `app/tasks/test_lab.py` |
| Observability | OpenTelemetry traces, Prometheus metrics | `app/core/tracing.py`, `observability/` |

The frontend (`frontend/src/app/`, ~34 pages) is a Next.js 14 application. It communicates exclusively through the API layer.

---

## Runtime Flows

### Agent invocation (direct call, not Test Lab)

```
Client
  |
  | POST /api/agents/{id}
  v
API Layer
  |
  |-- agent_registry_service.get_agent(db, agent_id)
  |       -> loads AgentDefinition from DB
  |
  |-- prompt_builder.build_agent_prompt(db, agent, runtime_context)
  |       -> 7-layer system prompt (see section below)
  |
  |-- agent_factory.get_tools_for_agent(agent_def)
  |       -> iterates agent.allowed_mcps
  |       -> obot_catalog_service.fetch_obot_server_by_id() per MCP
  |       -> checks OrkestraMCPBinding.enabled_in_orkestra
  |
  |-- agent_factory.create_agentscope_agent(agent_def, db, tools, max_iters)
  |       -> AgentScope ReActAgent + Toolkit
  |          (MCP tools + skills tools + sandbox if allow_code_execution=True)
  |
  |-- ReActAgent.run()  [Reason -> Act -> Observe, up to max_iters]
  |
  `-- result extracted from react_agent.memory.get_memory()
```

### Test Lab execution

```
Client
  |
  | POST /api/test-lab/scenarios/{id}/run
  v
API Layer
  |-- creates TestRun record (status=pending)
  `-- enqueues run_test_task(run_id, scenario_id) via Celery

Celery worker
  |
  `-- run_orchestrated_test(run_id, scenario_id, db)
        |
        |-- OrchestratorAgent  [ReActAgent, max_iters=12]
        |     Tools:
        |       get_scenario_context()      -- reads TestScenario + AgentDefinition
        |       run_scenario_subagent()     -- LLM produces structured test plan
        |       run_target_agent()          -- executes the real agent under test
        |       run_judge_subagent()        -- LLM scores output (0-100) + verdict + rationale
        |       run_robustness_subagent()   -- LLM proposes follow-up tests
        |       run_policy_subagent()       -- LLM checks governance compliance
        |       emit_event(type, data)      -- persists events to DB
        |       finalize_run(verdict, ...)  -- updates TestRun record
        |
        |  Each SubAgent: ReActAgent with max_iters=1
        |  (single LLM call, no ReAct loop)
        |
        `-- TestRun final state: completed | failed | timeout
            Score: 0-100
            Verdict: passed | failed | unknown

Client (UI)
  |
  `-- GET /api/test-lab/runs/{id}/stream   [SSE, real-time events]
```

---

## The 7-Layer Prompt Pipeline

`prompt_builder.build_agent_prompt()` assembles the system prompt in a fixed order. Each layer appends a labeled section to the prompt string.

| Layer | Section header | Source | Skipped when |
|-------|---------------|--------|--------------|
| 1 | FAMILY RULES | `family.default_system_rules` | Never |
| 2 | SKILL RULES | Each skill's `behavior_templates` + `output_guidelines` | Agent has no skills |
| 3 | SOUL | `agent.soul_content` | Field is empty |
| 4 | AGENT MISSION | `agent.name`, `purpose`, `description`, `prompt_content` | Never |
| 5 | OUTPUT EXPECTATIONS | `family.default_output_expectations` | Never |
| 6 | CONTRACTS | `agent.input_contract_ref`, `agent.output_contract_ref` | Both fields empty |
| 7 | RUNTIME CONTEXT | criticality, forbidden_effects (family union agent), allowed tools, limitations, runtime_context dict | Never |

Layer 7 is the primary mechanism through which governance constraints reach the model.

---

## Governance Model

### Declaration vs. enforcement

Forbidden effects are declared at two levels:

- `agent.forbidden_effects` — per-agent list of effect categories (e.g., `"external_write"`, `"financial_transaction"`)
- `family.default_forbidden_effects` — family-level defaults

At runtime, `prompt_builder` merges the two sets and injects the union into Layer 7 of the system prompt. The LLM reads this as a behavioral constraint.

**The API layer does not programmatically block calls based on forbidden effects.** Enforcement is model-behavioral, not code-enforced. There is no pre-execution check that refuses an invocation because the agent's action would violate a declared forbidden effect.

### Approval workflows

`ApprovalRequest` records exist in the database and are accessible through the API. They are not automatically created or evaluated during agent execution; they must be triggered manually.

### Audit trail

`AuditEvent` records are written by `audit_service.py` for:
- Agent definition changes
- Approval decisions
- Lifecycle state transitions

Records are immutable and stored in the `audit_events` table. There is no mechanism to delete or amend them.

---

## MCP Integration

Obot runs as a separate container at `http://obot:8080`.

```
obot_catalog_service.sync_obot_catalog()
  |
  |-- GET http://obot:8080/api/mcp-servers
  |-- upserts results into OrkestraMCPBinding table
  `-- result cached in Redis for 5 minutes

agent_factory.get_tools_for_agent(agent_def)
  |
  |-- reads agent.allowed_mcps (list of server IDs)
  |-- for each ID:
  |     checks OrkestraMCPBinding.enabled_in_orkestra
  |     fetches endpoint URL from Obot
  `-- registers tools via mcp_tool_registry.py into agent Toolkit
```

Each `OrkestraMCPBinding` record holds: `server_id`, `name`, `enabled_in_orkestra`, `family_bindings`, `workflow_bindings`.

**Obot unavailability behavior** is controlled by `OBOT_FALLBACK_TO_MOCK`:

| `OBOT_FALLBACK_TO_MOCK` | Effect when Obot is unreachable |
|-------------------------|--------------------------------|
| `true` | Mock responses returned silently; agent creation succeeds |
| `false` | Agent creation fails with an error |

---

## Memory Model

AgentScope `ReActAgent` maintains an in-memory `MemoryBase` per agent instance. Properties:

- Holds the full conversation history for the current run (user, assistant, tool_use, tool_result messages)
- Accessed via `react_agent.memory.get_memory()` after execution to extract output and tool call records
- Not persisted to the database between runs
- Not shared between different agent invocations
- Resets on each new run

There is no cross-run memory, vector store, or retrieval-augmented generation in the current implementation.

---

## Observability

| Signal | Emitter | Collector | Storage | UI |
|--------|---------|-----------|---------|-----|
| Traces | `app/core/tracing.py` (OpenTelemetry spans) | otel-collector | Tempo | Grafana |
| Metrics | `GET /api/metrics` (when `PROMETHEUS_ENABLED=true`) | Prometheus | Prometheus | Grafana |
| Logs | Python logging, structured | — | — | — |
| SSE events | `GET /api/test-lab/runs/{id}/stream` | — | DB (`emit_event`) | UI |

Log verbosity is controlled by the `ORKESTRA_LOG_LEVEL` environment variable.

---

## Trust Boundaries and Failure Points

| Boundary | What fails | Effect |
|----------|-----------|--------|
| Obot unreachable | MCP tool resolution | Agent creation fails, or uses mock responses (silent, if `OBOT_FALLBACK_TO_MOCK=true`) |
| Ollama unreachable | LLM calls | Agent run hangs or returns an error |
| Redis unreachable | Celery task dispatch | Test Lab runs cannot be queued; no execution starts |
| PostgreSQL unreachable | All database operations | API returns 500 on all routes |
| `FERNET_KEY` ephemeral | Secret decryption on restart | All secrets stored before the key change become invalid |
| Auth disabled | All API endpoints | Full API access without credentials |
| LLM non-determinism | Test Lab scoring | Same scenario can produce different scores and verdicts across runs |

---

## Component Boundaries (ASCII)

```
+------------------+       +---------------------+       +------------------+
|   Next.js UI     |       |   Obot container    |       |  Ollama / LLM    |
|  (34 pages)      |       |  http://obot:8080   |       |  (model backend) |
+--------+---------+       +---------+-----------+       +--------+---------+
         |  HTTP                     | HTTP (sync)                | HTTP
         v                           v                            v
+--------+---------------------------+-----------+----------------+---------+
|                        FastAPI (19 routers)                               |
|                           app/main.py                                     |
+---+-------------------+-------------------+-------------------+-----------+
    |                   |                   |                   |
    v                   v                   v                   v
+---+------+    +-------+------+    +-------+------+    +-------+------+
| Agent    |    | Test Lab     |    | Governance   |    | MCP          |
| Registry |    | (Celery task)|    | (Approval,   |    | Integration  |
| + Factory|    |              |    |  Audit)      |    | (Obot sync)  |
+---+------+    +-------+------+    +--------------+    +--------------+
    |                   |
    v                   v
+---+------+    +-------+------+
| Prompt   |    | Orchestrator |
| Builder  |    | Agent        |
| (7 layers)|   | (ReActAgent) |
+---+------+    +-------+------+
    |                   |
    +--------+----------+
             |
             v
    +--------+----------+
    |    PostgreSQL      |
    |  (single DB)       |
    +--------+----------+
             |
    +--------+----------+
    |  Redis (Celery +   |
    |  MCP catalog cache)|
    +--------------------+
```
