# Orkestra Mesh — Known Limitations (v0.1.0)

This document lists known limitations, incomplete features, and operational constraints in Orkestra Mesh v0.1.0. Reading it before using the system will prevent false expectations.

---

## Security limitations

### 1. Authentication is disabled in docker-compose.yml

`ORKESTRA_AUTH_ENABLED: "false"` is set explicitly in `docker-compose.yml`. All API endpoints are unauthenticated in the default development setup.

To enable: set `ORKESTRA_AUTH_ENABLED=true` and configure `ORKESTRA_API_KEYS`.

### 2. Default API key is public

`ORKESTRA_API_KEYS` defaults to `test-orkestra-api-key` in `app/core/config.py`. This key is committed to the repository — change it before any non-localhost deployment.

### 3. Ephemeral encryption key in development

When `ORKESTRA_FERNET_KEY` is not set, an ephemeral Fernet key is auto-generated at startup. All secrets stored in the database (`Secret` table) are encrypted with this key. On container restart, the key is lost and all stored secrets become undecryptable.

Warning logged at startup:
```
FERNET_KEY is not set. Secrets are encrypted with an ephemeral key that changes on every restart
```

Fix: set `ORKESTRA_FERNET_KEY` to a stable base64 Fernet key.

### 4. No role-based access control

API keys are binary (valid or invalid) — all valid keys have full API access. There is no concept of users, roles, or per-resource permissions.

### 5. Docker socket mounted

Both the `api` and `celery-worker` containers mount `/var/run/docker.sock`. This is required for the agent code execution sandbox (`sandbox_tool.py`) and Obot tool containers. It grants the container full control over the Docker daemon on the host.

---

## Governance enforcement limitations

### 6. `forbidden_effects` is advisory, not enforced

`agent.forbidden_effects` and `family.default_forbidden_effects` are declared in the database. At runtime, they are injected into the agent's system prompt as Layer 7 text instructions. No API-layer blocking exists — an LLM can ignore the constraint and perform forbidden effects. The API does not validate what tools the agent called after execution.

### 7. Approval workflows are manual

`ApprovalRequest` records can be created and resolved via the API. However, approval requests are NOT automatically triggered during agent execution. There is no mechanism that pauses agent execution and waits for human approval in the current implementation.

---

## Test Lab limitations

### 8. LLM evaluation is non-deterministic

Scores (0–100) and verdicts are produced by JudgeSubAgent (an LLM). The same scenario may produce different results on different runs. This is a fundamental property of LLM evaluation, not a bug.

### 9. Deterministic engines not active

`app/services/test_lab/scoring.py`, `assertion_engine.py`, and `diagnostic_engine.py` exist in the codebase. They are NOT called in the v0.2 pipeline — all evaluation goes through LLM SubAgents. They may be re-activated in a future version.

### 10. `tool_failure_rate` not computed

In `app/services/test_lab/agent_summary.py`:
```python
"tool_failure_rate": 0.0,  # TODO: compute from events
```
This metric is hardcoded. Agent summary stats do not accurately reflect tool failures.

### 11. Concurrent runs can overload Ollama

Ollama inference is single-threaded per model. Running 3+ test scenarios simultaneously causes timeouts and degraded scores. Recommendation: run scenarios sequentially when using a local Ollama instance.

---

## MCP and tool limitations

### 12. No local MCP server implementations

The `app/mcp_servers/` directory is empty. All MCP tool servers must run via Obot — Orkestra does not host tools natively.

### 13. Obot is a hard dependency

If Obot is unreachable and `OBOT_FALLBACK_TO_MOCK=true`, MCP tool calls silently return mock data. When `OBOT_FALLBACK_TO_MOCK=false`, agent creation fails if Obot is unavailable. Obot itself requires `OPENAI_API_KEY` to spawn tool containers.

### 14. MCP governance overlay is local metadata

`OrkestraMCPBinding.enabled_in_orkestra` disables tool availability in Orkestra's agent factory. This does not prevent direct access to the Obot tool server from outside Orkestra.

---

## Infrastructure limitations

### 15. Ollama is not containerized

Orkestra expects Ollama at `host.docker.internal:11434` (Docker host gateway). Ollama must be installed and running on the host machine separately. No automatic model download or version pinning is implemented.

### 16. Single Celery task type

`app/celery_app.py` registers only `app.tasks.test_lab`. Workflow execution (via the Plans/Runs API) is synchronous and not Celery-backed. Celery timeouts: soft limit 300 s, hard limit 600 s.

### 17. Development server flags in compose

`uvicorn ... --reload` is set in `docker-compose.yml` — this is not suitable for production use. `ORKESTRA_DEBUG: "true"` enables debug mode with verbose output.

---

## Agent memory limitations

### 18. No persistent memory between runs

AgentScope `ReActAgent` maintains in-memory conversation history per run only. Memory is not persisted to the database. Each new run starts with a clean memory — no context from previous runs.

### 19. No shared memory between agents

Multiple agents in a workflow do not share a common memory space. Each agent instance has its own isolated memory.

---

## Missing features

| # | Feature | Status |
|---|---|---|
| 20 | Multi-tenancy | Not implemented — single shared environment, no user accounts |
| 21 | Streaming inference | Not implemented — Ollama calls block until full response is received |
| 22 | Automatic retry on LLM failure | Not implemented — agent runs fail on LLM errors without retry |
| 23 | `base_service.py` | Stub — `app/services/base_service.py` is 2 lines; not a real base class |
| 24 | Plans/workflow execution | Incomplete — Plans and Runs API exists but full Celery-backed end-to-end execution is not implemented |
