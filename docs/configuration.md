# Orkestra Mesh — Configuration Reference

All environment variables use the prefix `ORKESTRA_`, defined in `app/core/config.py` with `env_prefix = "ORKESTRA_"`.

---

## Required for production

These variables have insecure defaults and **must be changed** before any production deployment.

| Variable | Default | Risk if unchanged |
|----------|---------|-------------------|
| `ORKESTRA_SECRET_KEY` | `orkestra-dev-secret-key-change-in-production` | Predictable token signing — any attacker who knows the default can forge tokens |
| `ORKESTRA_API_KEYS` | `test-orkestra-api-key` | Any caller who knows the default key has full API access |
| `ORKESTRA_FERNET_KEY` | (auto-generated at startup) | An ephemeral key is generated if this is empty — encrypted secrets are lost on restart |
| `ORKESTRA_AUTH_ENABLED` | `True` in code | Set to `false` in `docker-compose.yml` — must be explicitly set to `true` in production |

---

## Infrastructure

| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_DATABASE_URL` | `postgresql+asyncpg://orkestra:orkestra@localhost:5432/orkestra` | Async PostgreSQL URL used by FastAPI |
| `ORKESTRA_DATABASE_URL_SYNC` | `postgresql://orkestra:orkestra@localhost:5432/orkestra` | Sync PostgreSQL URL used by Alembic migrations |
| `ORKESTRA_REDIS_URL` | `redis://localhost:6379/0` | Redis — Celery broker and task result backend |
| `ORKESTRA_STORAGE_BACKEND` | `local` | Storage provider (`local` is the only supported value in the current version) |
| `ORKESTRA_STORAGE_LOCAL_PATH` | `./storage/documents` | Filesystem path for local file storage |

In `docker-compose.yml` the host references are overridden to use Docker service names (`postgres:5432`, `redis:6379`).

---

## LLM provider

| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_LLM_PROVIDER` | `ollama` | Active provider: `ollama` or `openai` |
| `ORKESTRA_OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint. In docker-compose: `http://host.docker.internal:11434` |
| `ORKESTRA_OLLAMA_MODEL` | `mistral` | Default model used when an agent does not specify one |
| `ORKESTRA_OPENAI_API_KEY` | (empty) | OpenAI or compatible API key |
| `ORKESTRA_OPENAI_MODEL` | `mistral-small-latest` | Default model for the OpenAI-compatible provider |
| `ORKESTRA_OPENAI_BASE_URL` | `https://api.mistral.ai/v1` | OpenAI-compatible endpoint (e.g., Mistral, local vLLM) |

---

## Obot

| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_OBOT_BASE_URL` | (empty) | Obot server URL. In docker-compose: `http://obot:8080` |
| `ORKESTRA_OBOT_API_KEY` | (empty) | Obot API key (required only if Obot has authentication enabled) |
| `ORKESTRA_OBOT_TIMEOUT_SECONDS` | `8.0` | HTTP timeout for Obot requests, in seconds |
| `ORKESTRA_OBOT_USE_MOCK` | `True` | Use mock Obot responses when a real Obot server is not configured |
| `ORKESTRA_OBOT_FALLBACK_TO_MOCK` | `True` | Fall back silently to mock responses on connection error |

In `docker-compose.yml`: `OBOT_USE_MOCK=false` and `OBOT_FALLBACK_TO_MOCK=false` — Obot is required and no silent fallback is allowed.

---

## Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ORKESTRA_PROMETHEUS_ENABLED` | `False` | Expose `/api/metrics` as a Prometheus scrape endpoint |
| `ORKESTRA_OTEL_ENDPOINT` | (empty) | OpenTelemetry collector URL (e.g., `http://otel-collector:4318/v1/traces`) |

In `docker-compose.yml`: `PROMETHEUS_ENABLED=true` and `OTEL_ENDPOINT=http://otel-collector:4318/v1/traces`.

---

## Authentication and CORS

| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_AUTH_ENABLED` | `True` (code) / `false` (compose) | Enable API key authentication middleware |
| `ORKESTRA_API_KEYS` | `test-orkestra-api-key` | Comma-separated list of valid API keys |
| `ORKESTRA_PUBLIC_PATHS` | `/api/health,/api/metrics,/docs,/openapi.json,/redoc` | Paths that bypass authentication |
| `ORKESTRA_CORS_ORIGINS` | `http://localhost:3000,http://localhost:3300,http://localhost:5173` | Comma-separated allowed CORS origins |

---

## Encryption

| Variable | Default | Description |
|----------|---------|-------------|
| `ORKESTRA_FERNET_KEY` | (auto-generated) | Base64-encoded Fernet key for encrypting secrets stored in the database. If left empty, an ephemeral key is generated at startup — all encrypted secrets are lost on restart. |

Generate a stable persistent key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store the output as `ORKESTRA_FERNET_KEY` in your environment or secrets manager.

---

## Docker Compose overrides

The `docker-compose.yml` deliberately overrides several code defaults for local development convenience. Be aware of these differences when moving from local to production:

| Variable | Code default | Docker Compose value | Reason |
|----------|-------------|---------------------|--------|
| `ORKESTRA_AUTH_ENABLED` | `True` | `false` | Simplify local development — no API key needed |
| `ORKESTRA_DEBUG` | `False` | `true` | Enable debug mode and detailed tracebacks |
| `ORKESTRA_OBOT_BASE_URL` | (empty) | `http://obot:8080` | Route to the `obot` Docker service |
| `ORKESTRA_OBOT_USE_MOCK` | `True` | `false` | Require a real Obot server |
| `ORKESTRA_OBOT_FALLBACK_TO_MOCK` | `True` | `false` | Disable silent fallback — surface real connection errors |
| `ORKESTRA_OLLAMA_HOST` | `http://localhost:11434` | `http://host.docker.internal:11434` | Reach Ollama running on the host machine |
| `ORKESTRA_PROMETHEUS_ENABLED` | `False` | `true` | Enable the `/api/metrics` endpoint |
| `ORKESTRA_OTEL_ENDPOINT` | (empty) | `http://otel-collector:4318/v1/traces` | Route traces to the otel-collector service |

> **Warning:** Never use the docker-compose environment in production. `AUTH_ENABLED=false` means the API is fully open. Always override `SECRET_KEY`, `API_KEYS`, `FERNET_KEY`, and `AUTH_ENABLED` in production deployments.
