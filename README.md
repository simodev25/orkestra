# Orkestra Mesh

A platform for defining, governing, and testing AI agents.

## What it is

Orkestra Mesh is a backend-first system that provides structured management of AI agents from definition through deployment. It is built around four concerns:

1. **Agent Registry** — agents are defined with structured metadata: system prompts, skills, allowed MCP tools, and governance constraints. A lifecycle state machine controls transitions (draft → active → deprecated).
2. **MCP Integration Layer** — agents connect to external tools via Obot's MCP catalog. A local governance overlay controls which tools are enabled per agent, with family and workflow bindings.
3. **Test Lab** — scenarios run against real agents (real LLM, real MCP tools) and are evaluated by LLM sub-agents acting as judge, policy checker, and robustness tester.
4. **Governance Layer** — approval workflows, audit logging, and lifecycle state management applied to all agent changes.

## What problem it solves

Most agent frameworks focus on runtime execution. Orkestra Mesh focuses on the layer before that: making agent definitions auditable, testable, and governable before they reach production. The Test Lab replaces manual prompt testing with structured scenarios evaluated by secondary LLMs.

## What makes it different

- Agents are versioned entities with a formal lifecycle, not ad-hoc prompt strings.
- Tool access is governed centrally via Obot's MCP catalog with per-agent overlays.
- Evaluation is structured: a scenario produces a score from an LLM judge, not a human eyeballing output.
- A 7-layer prompt pipeline assembles the final system prompt from reusable Families and Skills blocks.

## What is implemented (v0.1.0)

- Agent CRUD with metadata schema and lifecycle state machine
- Families and Skills system with prompt injection pipeline
- MCP tool catalog synchronization from Obot
- Test Lab: scenario definition, Celery-backed execution, LLM sub-agent evaluation
- Governance: approval workflow stubs, audit log entries
- 24 SQLAlchemy models, 18 Alembic migrations
- 44 test files covering core domain logic
- Observability stack: OpenTelemetry, Prometheus, Grafana, Tempo
- Frontend: Next.js 14 UI (~34 pages)

## What this does not do

- Does not run MCP servers locally — all MCP execution is delegated to Obot.
- Does not provide a production-grade auth system — auth is disabled by default.
- Does not containerize Ollama — it must run on the host.
- Does not back workflow execution with Celery — only Test Lab tasks use the queue.
- Does not provide deterministic evaluation — Test Lab scores vary across runs because evaluation is LLM-driven.
- Does not manage agent deployment to production endpoints.
- Is not production-ready in any configuration at this version.

## Repository status

| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Maturity | Experimental — development only |
| Models | 24 SQLAlchemy models |
| Migrations | 18 Alembic migrations |
| Tests | 44 test files |
| Production-ready | No |

## Tech stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.115+, Python 3.12 |
| Database | PostgreSQL 16, SQLAlchemy 2.0, AsyncPG |
| Async queue | Celery + Redis |
| LLM runtime | AgentScope ReActAgent (Ollama / OpenAI-compatible) |
| MCP tools | Obot catalog (external) |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Observability | OpenTelemetry + Prometheus + Grafana + Tempo |

## Services

| Service | Port | Description |
|---------|------|-------------|
| api (FastAPI) | 8200 | REST API |
| frontend (Next.js) | 3300 | Web UI |
| obot | 8080 | MCP catalog server |
| postgres | 5434 | Primary database |
| redis | 6382 | Broker and cache |
| grafana | 3100 | Dashboards |
| prometheus | 9190 | Metrics |

## Quickstart

**Prerequisites:**
- Docker and Docker Compose
- An OpenAI API key (required by Obot for tool containers)
- Ollama running on the host if using local models

```bash
git clone https://github.com/simodev25/orkestra.git
cd orkestra
cp .env.example .env
# Edit .env — at minimum set:
#   ORKESTRA_OPENAI_API_KEY=<your key>  (required by Obot for tool containers)
#   ORKESTRA_FERNET_KEY=<base64 key>    (optional in dev; required to persist secrets across restarts)

# Ensure Ollama is running on the host and the model is available:
ollama pull mistral
# Verify: ollama list  (should show mistral)

docker compose up -d
# Wait for startup (~30s), then verify:
curl http://localhost:8200/api/health
# Expected: {"status":"ok"} or similar

# Open the UI in your browser:
# http://localhost:3300
```

If `.env.example` is missing, create `.env` manually with the variables listed in `docs/configuration.md`.

## Security caveats — read before use

These are not optional warnings. They describe the current state of the system.

1. **Auth disabled by default.** `ORKESTRA_AUTH_ENABLED` is set to `"false"` in `docker-compose.yml`. All endpoints are unauthenticated unless you explicitly enable auth and configure it.

2. **Ephemeral encryption key.** `FERNET_KEY` is auto-generated at startup in dev mode. Any secrets stored in the database (e.g. API keys for MCP tools) are lost on container restart unless you set `ORKESTRA_FERNET_KEY` to a stable value in `.env`.

3. **Default API key is public.** The default key `test-orkestra-api-key` is in this repository. Change it before using Orkestra on any non-localhost network.

4. **Ollama is not containerized.** The LLM runtime expects Ollama at `host.docker.internal:11434`. You must start Ollama separately on the host and pull the model you intend to use.

5. **Obot dependency.** Obot requires `OPENAI_API_KEY` to run tool containers. If Obot is unavailable and `OBOT_FALLBACK_TO_MOCK=true`, tool calls will silently return mock responses with no error surfaced to the agent.

6. **Test Lab evaluation is non-deterministic.** LLM sub-agents (judge, policy checker, robustness tester) produce scores that vary between runs. The same scenario can score differently on repeated executions.

7. **Single Celery task type.** Only `app.tasks.test_lab` is registered with the queue. Workflow execution is synchronous, not Celery-backed.

## Architecture overview

Agents are defined in the registry with a system prompt, a set of Skills (reusable prompt blocks), a Family assignment, and a list of permitted MCP tools. When an agent is invoked, the 7-layer prompt pipeline assembles the final system prompt from these components.

The Test Lab accepts a scenario (a structured input + expected behavior description), executes it against the live agent, and passes the output to three LLM sub-agents for evaluation. Results are stored with a score, reasoning, and policy flags.

MCP tool access is mediated through Obot. The local governance overlay can enable or disable specific tools per agent and bind them to particular families or workflows.

For a full architectural description, see `docs/architecture.md`.

## Documentation

| Document | Content |
|----------|---------|
| `docs/architecture.md` | System design and data flow |
| `docs/getting-started.md` | Full setup guide |
| `docs/concepts.md` | Core concepts defined |
| `docs/agents.md` | Agent definition and lifecycle |
| `docs/test-lab.md` | Test Lab architecture and usage |
| `docs/configuration.md` | All environment variables |
| `docs/limitations.md` | Known gaps and caveats |
| `CONTRIBUTING.md` | Development setup |
| `SECURITY.md` | Security model |

## License

See `LICENSE` for terms.
