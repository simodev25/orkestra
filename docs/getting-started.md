# Getting Started with Orkestra Mesh

This guide walks you through cloning the repo, configuring your environment, starting all services, and creating your first agent. Follow every step in order.

---

## Prerequisites

You need the following before running anything:

**Docker and Docker Compose**
- Docker >= 24
- Docker Compose >= 2.20

Verify: `docker --version` and `docker compose version`

**Ollama (running on the host machine, not in Docker)**

Orkestra connects to Ollama at `http://host.docker.internal:11434`, which Docker resolves automatically to your host machine. Ollama must be running on the host — do not containerize it inside this project.

1. Install from https://ollama.com
2. Pull at least one model: `ollama pull mistral`
3. Verify it is available: `ollama list` — you should see `mistral` in the output
4. Keep Ollama running before starting Orkestra: `ollama serve`

**OpenAI API key**

Obot (the MCP catalog service) spawns tool containers using OpenAI-compatible APIs. Without a valid key, MCP tools will be unavailable. You do not need OpenAI for the core agent logic if you route through Ollama, but Obot requires this key to start its internal tooling layer.

**Git, and at least 4 GB RAM** available for containers.

---

## Clone the repository

```bash
git clone https://github.com/simodev25/orkestra.git
cd orkestra
```

---

## Environment setup

Copy the example env file:

```bash
cp .env.example .env
```

Open `.env` in your editor and set the following variables:

**Required:**

```
ORKESTRA_OPENAI_API_KEY=<your-openai-api-key>
```

Required by Obot. Without this, MCP tools will not be available.

**Optional but strongly recommended:**

```
ORKESTRA_FERNET_KEY=<base64-encoded-key>
```

Used to encrypt secrets at rest. If you leave this unset, secrets are encrypted with an ephemeral key that is regenerated on each restart — any stored credentials are lost when the api container restarts. In development this is tolerable; in any persistent environment set it explicitly.

Generate a key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output as the value of `ORKESTRA_FERNET_KEY`.

**Change the default API key:**

```
ORKESTRA_API_KEYS=<your-secret-key>
```

The default value is `test-orkestra-api-key`. This is intentionally insecure for development. Change it before exposing any endpoint to a network.

**Auth is disabled by default in the dev compose file** — `ORKESTRA_AUTH_ENABLED=false` is set in `docker-compose.yml`. All API endpoints are open without authentication. This is intentional for local development; do not run this configuration in production.

---

## Start services

```bash
docker compose up -d
```

Services start in the following dependency order:

1. **postgres** and **redis** — infrastructure, start first
2. **obot** — MCP catalog service, depends on postgres
3. **api** — FastAPI application; on startup it automatically runs `alembic upgrade head` (database migrations), then starts uvicorn with `--reload`
4. **celery-worker** — picks up background Celery tasks, depends on redis and api
5. **frontend** — React app served on port 3300; starts after the api health check passes

Migrations are idempotent — running `alembic upgrade head` multiple times is safe.

---

## Verify startup

Check that all containers are running:

```bash
docker compose ps
```

All services should show `running` or `healthy`. If any show `exited`, check logs immediately.

Check the API:

```bash
curl http://localhost:8200/api/health
```

Expected response: HTTP 200 with `{"status":"ok"}` or a similar status payload.

Check logs if something is wrong:

```bash
docker compose logs api --tail=50
docker compose logs obot --tail=30
```

---

## Common startup issues

**Ollama not reachable**

Symptom: API logs show connection errors to `host.docker.internal:11434`.

Fix: Make sure Ollama is running on your host machine. Run `ollama serve` in a terminal and leave it running. Then verify `ollama list` shows at least one model.

**Obot slow to start**

Obot can take 30–60 seconds to initialize. The `api` container waits for `obot: service_started` (not a healthcheck), so if the API comes up before Obot is fully ready, some MCP catalog requests will fail with a fallback to mock responses. This behavior is controlled by `OBOT_FALLBACK_TO_MOCK`. Wait a minute, then retry.

**Fernet warning in logs**

You will see this in the api logs if `ORKESTRA_FERNET_KEY` is not set:

```
FERNET_KEY is not set. Secrets are encrypted with an ephemeral key...
```

This is expected in development. Set `ORKESTRA_FERNET_KEY` (see above) to suppress it and persist secrets across restarts.

**Migrations already applied**

If you see Alembic output saying migrations are already at head, that is fine. `alembic upgrade head` is idempotent.

**Port conflicts**

Orkestra uses these host ports by default:

| Service  | Host port |
|----------|-----------|
| api      | 8200      |
| frontend | 3300      |
| postgres | 5434      |
| redis    | 6382      |

If any of these are in use by another process, stop the conflicting process or modify the `ports:` mappings in `docker-compose.yml`.

---

## Access the UI

Open your browser at: http://localhost:3300

The frontend communicates with the API at `http://localhost:8200`. No login is required by default — auth is disabled in the dev compose configuration.

---

## Access the API

- API base URL: http://localhost:8200
- Swagger UI (interactive docs): http://localhost:8200/docs

With auth disabled, all endpoints are open with no headers required.

When auth is enabled (`ORKESTRA_AUTH_ENABLED=true`), include this header in every request:

```
X-API-Key: test-orkestra-api-key
```

Change this value in production by setting `ORKESTRA_API_KEYS` in your `.env`.

---

## Seed data

On first startup, the FastAPI lifespan event automatically runs `seed_service.seed_all(db)`. This loads:

- `app/config/families.seed.json` → `FamilyDefinition` records in the database
- `app/config/skills.seed.json` → `SkillDefinition` records into the in-memory registry (not persisted to the database)

The seed is idempotent — it uses upserts and will never overwrite manual changes you make after the initial load.

---

## Create your first agent

**Via the UI:**

1. Open http://localhost:3300
2. Navigate to **Agents** → **New Agent**
3. Fill in: name, family (select from the seeded families), purpose, and system prompt
4. Add skills from the skills catalog
5. Add allowed MCP tools (from the Obot catalog, if Obot is running and healthy)
6. Save as draft
7. Advance the lifecycle: `draft` → `designed` → `tested` → `registered` → `active`

**Via the API:**

```bash
curl -X POST http://localhost:8200/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my_first_agent",
    "name": "My First Agent",
    "family_id": "analysis",
    "purpose": "Demonstrate basic agent creation",
    "prompt_content": "You are a helpful assistant."
  }'
```

Replace `"family_id": "analysis"` with a family ID that exists in your seeded data. You can list available families at `GET http://localhost:8200/api/families`.

---

## Running tests

From your local Python environment (requires Python 3.11+):

```bash
pip install -e ".[dev]"
pytest tests/ -x -v --asyncio-mode=auto
```

Or inside the running api container:

```bash
docker compose exec api pytest tests/ -x --asyncio-mode=auto
```

---

## Next steps

- `docs/concepts.md` — how agents, families, skills, and MCPs relate to each other
- `docs/agents.md` — full agent definition schema and lifecycle states
- `docs/test-lab.md` — set up and run your first test scenario
- `docs/configuration.md` — all environment variables and their defaults
- `docs/limitations.md` — known limitations; read before using in any serious context
