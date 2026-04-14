# Documentation Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite Orkestra Mesh's documentation from scratch so that it is technically accurate, honest about limitations, and useful to engineers discovering the project.

**Architecture:** The repo has no README. Existing docs (TEST_LAB_ARCHITECTURE.md, SKILLS_IMPLEMENTATION.md, families-skills-prompt-architecture.md) are good internal references but not user-facing. The new doc set creates a complete, accurate public-facing documentation tree rooted at README.md and the docs/ directory.

**Tech Stack:** Markdown, no tooling required — write files directly. Cross-reference actual file paths, env vars, and commands from the codebase.

---

## Audit Summary (Phase 1)

### What is clearly implemented
- Agent registry with versioning, lifecycle state machine (draft→designed→tested→registered→active→deprecated/disabled→archived)
- Families and Skills system (seed JSON → DB, prompt injection via 7-layer builder)
- MCP integration via Obot catalog (sync, local bindings, governance overlay)
- Test Lab v0.2 — multi-agent agentic testing (OrchestratorAgent + 4 SubAgents, 100% LLM-driven evaluation)
- Approval workflows, audit logging, agent control (pause/resume/terminate)
- Secrets storage (Fernet encrypted in DB)
- Celery async task queue (Redis broker — 1 registered task type: test_lab)
- OpenTelemetry tracing + Prometheus + Tempo + Grafana (full observability stack)
- API key authentication middleware
- Docker Compose with 9 services (postgres, redis, obot, api, celery-worker, frontend, otel-collector, tempo, prometheus/grafana)
- Next.js frontend with ~34 pages
- 44 test files

### What is partially implemented / has known gaps
- `mcp_servers/` directory is empty — no local MCP server implementations; all MCP via Obot
- `base_service.py` is a 2-line stub
- Deterministic assertion/scoring/diagnostic engines exist in code but are NOT called in v0.2 pipeline — evaluation is 100% LLM-driven
- `tool_failure_rate` in agent_summary.py is hardcoded `0.0` with a TODO comment
- Celery only registers `app.tasks.test_lab` — workflow/orchestration tasks not in Celery
- Governance: `forbidden_effects` declared at agent level but runtime enforcement is advisory (LLM prompt injection), not hard-blocked at API layer
- Plans/workflow execution service exists but coupling with Celery is unclear
- Obot dependency: if Obot is unavailable, `OBOT_FALLBACK_TO_MOCK` controls whether tools silently fail

### What current docs overstate (old AUDIT_REPORT.md, 2026-04-07 vintage)
- "Zero authentification" — now fixed (ApiKeyMiddleware implemented)
- "Secrets stored in clair" — now fixed (Fernet encryption)
- "6 tables sans migrations" — now fixed (18 migrations including Test Lab tables)
- AUDIT_REPORT.md is a historical artifact; should not be used as reference

### Non-obvious operational constraints
- Ollama must run on the **host machine** (`host.docker.internal:11434`), it is not containerized
- Auth is **disabled** in docker-compose dev config (`ORKESTRA_AUTH_ENABLED: "false"`)
- `FERNET_KEY` auto-generates ephemerally in dev — all secrets are lost on restart unless `ORKESTRA_FERNET_KEY` is set
- Default API key is `test-orkestra-api-key` — must be changed before any non-local use
- Obot requires `OPENAI_API_KEY` to function (tool containers use OpenAI)
- `--reload` is used in dev uvicorn — not for production

---

## File Structure

**New files to create:**
- `README.md` — project overview, quickstart, components, limitations map
- `docs/architecture.md` — subsystems, data flow, runtime flow diagram
- `docs/getting-started.md` — prerequisites, env setup, docker compose up, first agent
- `docs/concepts.md` — agents, families, skills, MCPs, test lab concepts defined precisely
- `docs/agents.md` — agent definition fields, lifecycle, factory, prompt composition
- `docs/test-lab.md` — replaces/consolidates TEST_LAB_ARCHITECTURE.md (in English, updated)
- `docs/configuration.md` — all env vars with types, defaults, requirements
- `docs/limitations.md` — honest gaps, caveats, known issues
- `CONTRIBUTING.md` — how to contribute, dev setup, testing
- `SECURITY.md` — security model, what is and is not guaranteed

**Files to keep (already accurate):**
- `docs/SKILLS_IMPLEMENTATION.md` — accurate, keep
- `docs/families-skills-prompt-architecture.md` — accurate, keep
- `docs/TEST_LAB_ARCHITECTURE.md` — accurate internal reference, keep but add deprecation note pointing to docs/test-lab.md

**Files to delete or clearly mark as historical:**
- `AUDIT_REPORT.md` — historical artifact from pre-refactor; add header note

---

## Task 1: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

Content spec (every section must be backed by code evidence):

```markdown
# Orkestra Mesh

A platform for defining, governing, and testing AI agents — with lifecycle management,
MCP tool integration, and an agentic test lab.

## What it does

- **Agent registry**: define agents with structured metadata, system prompts, skills, 
  allowed MCP tools, governance constraints, and lifecycle states
- **MCP integration**: connect agents to external tools via Obot's MCP catalog; 
  apply local governance overlays (enable/disable, family/workflow bindings)
- **Test Lab**: run a scenario against a real agent (real LLM, real MCP tools) 
  and evaluate the output using LLM SubAgents (judge, policy checker, robustness tester)
- **Governance layer**: approval workflows, audit logging, lifecycle state machine 
  (draft → designed → tested → registered → active → deprecated/disabled → archived)
- **Families and Skills**: reusable capability blocks injected into agent system prompts 
  via a 7-layer prompt composition pipeline

## What it does not do

- Execute live financial transactions or autonomous actions on external systems
- Guarantee runtime enforcement of `forbidden_effects` — governance is advisory 
  (injected in agent prompt) not hard-blocked at API layer
- Provide a production-ready deployment — auth is disabled in docker-compose dev config
- Include a local Ollama instance — you must run Ollama separately on the host machine
- Include local MCP server implementations — all tools come from Obot's catalog

## Repository status

Version: 0.1.0 — **Development / experimental**

This project is not production-ready. It contains:
- Hardcoded default secrets that must be replaced before any non-local use
- Authentication disabled by default in `docker-compose.yml`
- Ephemeral secret encryption key in dev (secrets lost on restart)
- LLM-only test evaluation (no deterministic assertion pipeline)
- A single Celery task type (test execution) — workflow automation is not Celery-backed

## Architecture overview

(brief diagram + components list)

## Quickstart

Prerequisites:
- Docker + Docker Compose
- Ollama running locally with at least one model (e.g., `ollama pull mistral`)
- OpenAI API key (required by Obot for tool containers)

Steps:
1. Clone the repo
2. Copy `.env.example` to `.env`
3. Set `OPENAI_API_KEY` in `.env`
4. `docker compose up -d`
5. Wait for health check: `curl http://localhost:8200/api/health`
6. Open http://localhost:3300

## Components

| Component | Port | Description |
|-----------|------|-------------|
| API (FastAPI) | 8200 | REST API + WebSocket |
| Frontend (Next.js) | 3300 | Web UI |
| Obot | 8080 | MCP catalog server |
| PostgreSQL | 5434 | Primary database |
| Redis | 6382 | Broker + cache |
| Grafana | 3100 | Observability dashboards |
| Prometheus | 9190 | Metrics collection |

## Current limitations

See `docs/limitations.md` for a complete list. Key items:
- Auth disabled in dev — enable with `ORKESTRA_AUTH_ENABLED=true`
- Set `ORKESTRA_FERNET_KEY` in production (auto-generated key is ephemeral)
- Ollama must run on the host machine, not containerized
- Test Lab evaluation is 100% LLM-driven; results vary with model

## Documentation map

| Document | Content |
|----------|---------|
| docs/architecture.md | System design, data flow, runtime flow |
| docs/getting-started.md | Full setup guide |
| docs/concepts.md | Core concepts defined |
| docs/agents.md | Agent definition, lifecycle, prompt composition |
| docs/test-lab.md | Test Lab architecture and usage |
| docs/configuration.md | All environment variables |
| docs/limitations.md | Known gaps and caveats |
| CONTRIBUTING.md | Development setup |
| SECURITY.md | Security model |

## License

[see LICENSE file if present]
```

- [ ] **Step 2: Verify README is accurate**

For each claim, confirm the backing evidence:
- "Agent registry with lifecycle states" → `app/state_machines/agent_lifecycle_sm.py` + `app/models/registry.py`
- "MCP via Obot" → `app/services/obot_catalog_service.py`
- "Test Lab with LLM SubAgents" → `app/services/test_lab/orchestrator_agent.py`
- "Auth disabled in dev" → `docker-compose.yml` `ORKESTRA_AUTH_ENABLED: "false"`
- "Ollama not containerized" → `docker-compose.yml` `ORKESTRA_OLLAMA_HOST: http://host.docker.internal:11434`
- "Single Celery task type" → `app/celery_app.py` `include=["app.tasks.test_lab"]`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: create README.md — accurate project overview from codebase audit"
```

---

## Task 2: docs/architecture.md

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Write docs/architecture.md**

Sections:
1. **System overview** — what the system is for; 3-sentence summary
2. **Subsystems** — table: name, responsibility, key files
3. **Runtime flow — agent execution** — step-by-step: request → registry load → MCP resolution → AgentScope agent creation → ReActAgent loop → result
4. **Runtime flow — Test Lab execution** — Celery task → OrchestratorAgent → TargetAgentRunner → SubAgent evaluation → DB persist → SSE stream
5. **Data flow** — who writes what to where
6. **Governance model** — where rules are declared, where they are applied (advisory vs. enforced), approval workflow
7. **Prompt composition** — the 7-layer system (Family Rules → Skills → Soul → Mission → Output Expectations → Contracts → Runtime Context)
8. **MCP integration** — Obot catalog sync → local bindings → agent resolution → tool invocation
9. **Observability** — OpenTelemetry spans, Prometheus metrics, Tempo traces, Grafana dashboards
10. **Trust boundaries and failure points** — Obot unavailable, Ollama unavailable, LLM non-determinism, ephemeral FERNET_KEY

Key facts to include:
- Agent creation: `app/services/agent_factory.py` `create_agentscope_agent()`
- Memory: AgentScope in-memory conversation history per run (not persisted between runs)
- Prompt builder: `app/services/prompt_builder.py` `build_agent_prompt()`
- Governance declaration: `agent.forbidden_effects` + `family.default_forbidden_effects`
- Governance enforcement: injected as Layer 7 of system prompt — model reads it, API does NOT block on it
- MCP resolution: `obot_catalog_service.fetch_obot_server_by_id()` + `OrkestraMCPBinding.enabled_in_orkestra`
- Celery broker: Redis at `ORKESTRA_REDIS_URL`

- [ ] **Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: create architecture.md — accurate subsystem and data flow documentation"
```

---

## Task 3: docs/getting-started.md

**Files:**
- Create: `docs/getting-started.md`

- [ ] **Step 1: Write docs/getting-started.md**

Sections:
1. **Prerequisites** — exact requirements:
   - Docker >= 24, Docker Compose >= 2.20
   - Ollama >= 0.1.30 running on the host with at least one model (`ollama pull mistral`)
   - OpenAI API key (required by Obot)
   - 4GB+ RAM for containers
2. **Clone and configure** — actual commands:
   ```bash
   git clone https://github.com/simodev25/orkestra.git
   cd orkestra
   cp .env.example .env
   # Edit .env: set ORKESTRA_OPENAI_API_KEY
   ```
3. **Start services** — `docker compose up -d`
4. **Verify startup** — health check commands for each service
5. **Run database migrations** — `docker compose exec api alembic upgrade head` (already done automatically in compose but document explicitly)
6. **Access the UI** — http://localhost:3300
7. **API access** — curl example with default API key
8. **Seed data** — explain that families and skills seed automatically on startup
9. **Create your first agent** — UI walkthrough steps
10. **Known startup issues** — Obot startup time, Ollama not reachable, FERNET_KEY warning

Include actual env var names and defaults from `app/core/config.py`.
Include actual port mappings from `docker-compose.yml`.
Include the warning: auth is disabled in dev compose — `ORKESTRA_AUTH_ENABLED: "false"`.

- [ ] **Step 2: Commit**

```bash
git add docs/getting-started.md
git commit -m "docs: create getting-started.md — precise setup guide from docker-compose"
```

---

## Task 4: docs/concepts.md

**Files:**
- Create: `docs/concepts.md`

- [ ] **Step 1: Write docs/concepts.md**

Define each concept precisely, grounded in the actual model fields:

**Agent** — an `AgentDefinition` record in the registry. Contains: id, name, family_id, purpose, allowed_mcps, forbidden_effects, prompt_content, skills, llm_provider, llm_model, lifecycle status. An agent definition is a blueprint; runtime execution creates an in-memory `ReActAgent` (AgentScope) from it.

**Family** — a `FamilyDefinition` grouping agents by operational context. Contributes `default_system_rules` (prompt Layer 1) and `default_forbidden_effects` (merged into Layer 7). Every agent must belong to exactly one active family.

**Skill** — a `SkillDefinition` reusable capability block. Carries `behavior_templates` and `output_guidelines` injected into prompt Layer 2. Scoped by `allowed_families` — a skill can only be assigned to agents whose family is in its allow-list.

**MCP (Model Context Protocol)** — a tool server accessible to agents. Orkestra manages MCPs as `MCPDefinition` records with governance overlays (`OrkestraMCPBinding`). MCP servers themselves run via Obot. Agents declare which MCPs they are allowed to use via `allowed_mcps`.

**Test Scenario** — a `TestScenario` record defining: input_prompt, expected assertions, tags, allowed_tools, timeout, max_iterations. Running a scenario creates a `TestRun`.

**Test Run** — a `TestRun` record representing one execution of a scenario against an agent. Evaluated by the OrchestratorAgent (LLM-driven). Results: status, verdict (passed/failed/unknown), score (0–100), assertion_results, final_output.

**Approval** — an `ApprovalRequest` record created when an agent action requires human sign-off. Resolved by an approver via `POST /api/approvals/{id}/approve` or `/reject`.

**Forbidden Effects** — a list of action categories (e.g., "external_write", "financial_transaction") declared on an agent and its family. Injected into the agent's system prompt as behavioral constraints. NOT enforced at the API execution layer.

**Lifecycle State** — the current stage of an agent in the development pipeline: `draft → designed → tested → registered → active → deprecated/disabled → archived`. Transitions are validated by the state machine in `app/state_machines/agent_lifecycle_sm.py`.

- [ ] **Step 2: Commit**

```bash
git add docs/concepts.md
git commit -m "docs: create concepts.md — precise definitions from ORM models and state machines"
```

---

## Task 5: docs/agents.md

**Files:**
- Create: `docs/agents.md`

- [ ] **Step 1: Write docs/agents.md**

Sections:
1. **Agent definition fields** — table of every field in `AgentDefinition` with type, default, description, and whether it affects prompt composition
2. **Agent lifecycle** — state machine diagram (text-based), what each transition requires
3. **Agent factory** — how `create_agentscope_agent()` works: loads definition → resolves MCP tools → resolves skills → creates `ReActAgent` with `Toolkit` → registers memory
4. **Prompt composition** — the 7-layer pipeline from `app/services/prompt_builder.py`:
   - Layer 1: Family Rules (`family.default_system_rules`)
   - Layer 2: Skill Rules (each skill's `behavior_templates` + `output_guidelines`)
   - Layer 3: Soul (`agent.soul_content` — skipped if empty)
   - Layer 4: Agent Mission (`agent.name`, `purpose`, `description`, `prompt_content`)
   - Layer 5: Output Expectations (`family.default_output_expectations`)
   - Layer 6: Contracts (`agent.input_contract_ref`, `agent.output_contract_ref` — skipped if both empty)
   - Layer 7: Runtime Context (criticality, forbidden effects union, allowed tools, limitations, runtime context dict)
5. **MCP tool resolution** — how `get_tools_for_agent()` resolves tools from `allowed_mcps`
6. **Code execution** — sandbox via `allow_code_execution=True` → Docker container (`python:3.12-slim`)
7. **LLM provider** — `llm_provider` + `llm_model` fields; Ollama vs. OpenAI-compatible
8. **Governance** — `forbidden_effects` declared vs. enforced; approval gates; audit logging
9. **Versioning** — `AgentDefinitionHistory` table, `GET /api/agents/{id}/history`, `POST /api/agents/{id}/restore/{history_id}`

- [ ] **Step 2: Commit**

```bash
git add docs/agents.md
git commit -m "docs: create agents.md — agent definition, lifecycle, factory, and prompt pipeline"
```

---

## Task 6: docs/test-lab.md

**Files:**
- Create: `docs/test-lab.md`

Note: This replaces `docs/TEST_LAB_ARCHITECTURE.md` as the user-facing reference. TEST_LAB_ARCHITECTURE.md stays as internal design reference.

- [ ] **Step 1: Write docs/test-lab.md**

Translate and update `docs/TEST_LAB_ARCHITECTURE.md` into English, with corrections:

Sections:
1. **What the Test Lab does** — scenario-based testing of real agents (real LLM, real MCP tools, LLM evaluation)
2. **Key architectural fact** — evaluation is 100% LLM-driven; deterministic engines (`scoring.py`, `assertion_engine.py`, `diagnostic_engine.py`) exist in code but are not called in v0.2 pipeline
3. **Agents in the Test Lab**:
   - `TargetAgent` — the agent under test (resolved from registry, real execution)
   - `OrchestratorAgent` — ReActAgent with 8 tools, `max_iters=12`, coordinates the run
   - `ScenarioSubAgent` — prepares test plan (LLM, `max_iters=1`)
   - `JudgeSubAgent` — evaluates output, produces verdict + score + rationale (LLM, `max_iters=1`)
   - `RobustnessSubAgent` — proposes follow-up tests (LLM, `max_iters=1`)
   - `PolicySubAgent` — checks governance compliance (LLM, `max_iters=1`)
4. **Execution flow** — step by step: API → Celery → OrchestratorAgent → TargetAgentRunner → SubAgents → DB → SSE
5. **Scenario definition** — fields: input_prompt, assertions, tags, allowed_tools, timeout_seconds, max_iterations
6. **Run lifecycle** — pending → running → completed/failed/timeout; events stream via SSE
7. **Scoring** — score is 0–100 from JudgeSubAgent; assertion_results from PolicySubAgent; verdict is passed/failed/unknown
8. **Configuration** — `GET/PUT /api/test-lab/config` controls model, prompts for each SubAgent
9. **Interactive chat** — after a run, `POST /api/test-lab/runs/{id}/chat` continues conversation with OrchestratorAgent
10. **Known limitations**:
    - LLM evaluation is non-deterministic — same scenario can score differently on repeated runs
    - Concurrent test runs can cause load issues with local Ollama
    - `tool_failure_rate` metric is hardcoded 0.0 (not yet computed from events)

- [ ] **Step 2: Add deprecation notice to TEST_LAB_ARCHITECTURE.md**

Add at top of `docs/TEST_LAB_ARCHITECTURE.md`:
```markdown
> **Note:** This is an internal design reference document (v0.2, French). 
> The user-facing documentation is at `docs/test-lab.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/test-lab.md docs/TEST_LAB_ARCHITECTURE.md
git commit -m "docs: create test-lab.md (EN) — accurate test lab reference from architecture doc"
```

---

## Task 7: docs/configuration.md

**Files:**
- Create: `docs/configuration.md`

- [ ] **Step 1: Write docs/configuration.md**

Create a configuration reference with a table for every env var in `app/core/config.py`.

Format each section:

**Required for production** (must change from defaults):
| Variable | Default | Description | Risk if not changed |
|----------|---------|-------------|---------------------|
| `ORKESTRA_SECRET_KEY` | `orkestra-dev-secret-key-change-in-production` | JWT signing key | Predictable token signing |
| `ORKESTRA_API_KEYS` | `test-orkestra-api-key` | Comma-separated valid API keys | Open API access |
| `ORKESTRA_FERNET_KEY` | (auto-generated) | Base64 Fernet key for secret encryption | Secrets lost on restart |
| `ORKESTRA_AUTH_ENABLED` | `True` (but `false` in compose) | Enable API key middleware | All endpoints unprotected |

**Infrastructure** (change for your environment):
| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_DATABASE_URL` | postgresql+asyncpg://orkestra:orkestra@localhost:5432/orkestra | Async DB URL |
| `ORKESTRA_DATABASE_URL_SYNC` | postgresql://orkestra:... | Sync DB URL (Alembic migrations) |
| `ORKESTRA_REDIS_URL` | redis://localhost:6379/0 | Redis broker + Celery backend |

**LLM provider**:
| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `ORKESTRA_OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `ORKESTRA_OLLAMA_MODEL` | `mistral` | Default Ollama model |
| `ORKESTRA_OPENAI_API_KEY` | (empty) | OpenAI or compatible API key |
| `ORKESTRA_OPENAI_MODEL` | `mistral-small-latest` | Default OpenAI-compatible model |
| `ORKESTRA_OPENAI_BASE_URL` | `https://api.mistral.ai/v1` | OpenAI-compatible endpoint |

**Obot**:
| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_OBOT_BASE_URL` | (empty) | Obot server URL (e.g., `http://obot:8080`) |
| `ORKESTRA_OBOT_API_KEY` | (empty) | Obot API key |
| `ORKESTRA_OBOT_USE_MOCK` | `True` | Use mock Obot if real unavailable |
| `ORKESTRA_OBOT_FALLBACK_TO_MOCK` | `True` | Fall back to mock on connection error |
| `ORKESTRA_OBOT_TIMEOUT_SECONDS` | `8.0` | Obot request timeout |

**Observability**:
| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_LOG_LEVEL` | `INFO` | Logging verbosity |
| `ORKESTRA_PROMETHEUS_ENABLED` | `False` | Expose /api/metrics |
| `ORKESTRA_OTEL_ENDPOINT` | (empty) | OpenTelemetry collector URL |

Include a section: **Docker Compose overrides** explaining which vars are overridden in compose and why (especially AUTH_ENABLED=false).

- [ ] **Step 2: Commit**

```bash
git add docs/configuration.md
git commit -m "docs: create configuration.md — complete env var reference from config.py"
```

---

## Task 8: docs/limitations.md

**Files:**
- Create: `docs/limitations.md`

- [ ] **Step 1: Write docs/limitations.md**

This is the most important credibility document. Every item must be backed by code evidence.

Sections and items:

**Security**
- Auth disabled in docker-compose dev (`ORKESTRA_AUTH_ENABLED: "false"`) — all endpoints unprotected
- Default API key `test-orkestra-api-key` must be rotated before any non-local use
- `FERNET_KEY` auto-generates ephemerally — secrets are lost on API restart in dev
- `SECRET_KEY` has a hardcoded default — must be replaced in production

**Governance enforcement**
- `forbidden_effects` are declared at the agent/family level but enforced only via prompt injection (Layer 7 of system prompt) — an LLM can still violate them
- No API-layer blocking exists for forbidden effect types at runtime execution
- Approval workflows exist in the DB and API but are not automatically triggered during agent execution — they must be manually invoked

**Test Lab**
- Evaluation is 100% LLM-driven — `scoring.py`, `assertion_engine.py`, `diagnostic_engine.py` exist but are not called in the v0.2 pipeline
- LLM evaluation is non-deterministic — the same scenario can produce different scores on repeated runs
- `tool_failure_rate` is hardcoded `0.0` in agent_summary aggregation (TODO)
- Concurrent test runs (≥3 simultaneous) can overload a local Ollama instance

**MCP integration**
- All MCP servers come from Obot — no local MCP server implementations (`mcp_servers/` directory is empty)
- If Obot is unavailable and `OBOT_FALLBACK_TO_MOCK=true`, tool calls silently return mock data
- Obot requires an OpenAI API key for tool containers

**Infrastructure**
- Ollama runs on the host machine (`host.docker.internal:11434`) — not containerized, not in the compose stack
- Celery only registers 1 task type: `app.tasks.test_lab` — workflow/orchestration execution is not Celery-backed
- `--reload` flag in dev uvicorn — not appropriate for production

**Code quality**
- `base_service.py` is a 2-line stub
- Plans/workflow execution API exists but is not fully wired to Celery task execution

**Missing features**
- No multi-tenancy or user accounts — single shared environment
- No rate limiting per agent or per scenario
- No persistent agent memory across runs (memory is in-memory per AgentScope session)
- No streaming from Ollama (inference blocks until complete)

- [ ] **Step 2: Commit**

```bash
git add docs/limitations.md
git commit -m "docs: create limitations.md — honest caveats and gaps from codebase audit"
```

---

## Task 9: CONTRIBUTING.md

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Write CONTRIBUTING.md**

Sections:
1. **Development setup** — Python 3.12 + venv + `pip install -e ".[dev]"`, Node.js 20 for frontend
2. **Running the test suite** — `pytest tests/ -x -v --asyncio-mode=auto`
3. **Running the backend locally** — without Docker: requires postgres + redis + ollama
4. **Running the frontend** — `cd frontend && npm install && npm run dev`
5. **Database migrations** — `alembic upgrade head`, how to create a new migration
6. **Code conventions** — Python: ruff/black formatting; TypeScript: ESLint; no mock fallbacks
7. **Pull request checklist** — tests pass, migrations included if schema changed, env vars documented
8. **Project structure** — brief map of which directory does what

Use actual commands from `pyproject.toml` and `docker-compose.yml`.

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: create CONTRIBUTING.md — dev setup and contribution guide"
```

---

## Task 10: SECURITY.md

**Files:**
- Create: `SECURITY.md`

- [ ] **Step 1: Write SECURITY.md**

Sections:
1. **Authentication** — API key middleware (`app/core/auth.py`); disabled by default in dev compose; enable with `ORKESTRA_AUTH_ENABLED=true`
2. **Secret storage** — Fernet encryption (`app/services/secret_service.py`); key auto-generated in dev (ephemeral); set `ORKESTRA_FERNET_KEY` for persistence
3. **What is NOT guaranteed** — be explicit:
   - Governance `forbidden_effects` is prompt-level only, not API-enforced
   - No role-based access control — API keys are binary (valid/invalid)
   - No audit of who holds an API key — all valid keys have full access
   - Docker socket access (`/var/run/docker.sock`) is required for sandbox containers — this is a high-privilege mount
4. **Code execution sandbox** — Python code runs in `python:3.12-slim` Docker containers; isolation via container boundaries
5. **Reporting security issues** — provide contact method or GitHub issue template
6. **Default credentials** — list all defaults that must be changed

- [ ] **Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: create SECURITY.md — honest security model and limitations"
```

---

## Task 11: Mark AUDIT_REPORT.md as historical

**Files:**
- Modify: `AUDIT_REPORT.md`

- [ ] **Step 1: Add historical notice**

Add at the very top of `AUDIT_REPORT.md`:

```markdown
> **Historical document — 2026-04-07 (pre-refactor)**
> 
> This audit was conducted before several critical fixes were implemented:
> - Authentication middleware has since been added (`app/core/auth.py`)
> - Secret encryption (Fernet) has been implemented
> - All Test Lab migrations have been added (18 migrations total)
> - Deterministic assertion engines have been implemented (though not active in v0.2 pipeline)
> 
> The current limitations and status are documented in `docs/limitations.md`.
> Do not use this document as a current reference.
```

- [ ] **Step 2: Commit**

```bash
git add AUDIT_REPORT.md
git commit -m "docs: mark AUDIT_REPORT.md as historical — superseded by docs/limitations.md"
```

---

## Self-Review

**Spec coverage check:**
- ✅ README.md → Task 1
- ✅ docs/architecture.md → Task 2
- ✅ docs/getting-started.md → Task 3
- ✅ docs/concepts.md → Task 4
- ✅ docs/agents.md → Task 5
- ✅ docs/test-lab.md → Task 6
- ✅ docs/configuration.md → Task 7
- ✅ docs/limitations.md → Task 8
- ✅ CONTRIBUTING.md → Task 9
- ✅ SECURITY.md → Task 10
- ✅ AUDIT_REPORT.md cleanup → Task 11

Spec items NOT covered (would need maintainer input):
- `docs/runtime-flow.md` — merged into architecture.md
- `docs/memory.md` — no persistent memory in current codebase; documented in limitations.md
- `docs/risk-and-governance.md` — merged into agents.md and limitations.md
- `docs/observability.md` — defer; basic coverage in architecture.md
- `docs/execution.md` — deferred; not fully implemented (workflow Celery)
- `docs/quickstart.md` — merged into getting-started.md

**Placeholder scan:** No TBDs, no "implement later" patterns. All steps reference actual file paths and actual commands.

**Type consistency:** No code — all markdown. File paths verified against codebase audit.
