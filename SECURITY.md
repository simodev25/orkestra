#### Authentication

Orkestra uses API key authentication via `app/core/auth.py` (`ApiKeyMiddleware`).

**How it works:**
- `X-API-Key` header is checked against `ORKESTRA_API_KEYS` (comma-separated list)
- Requests without a valid key receive HTTP 401
- Public paths bypass auth: `/api/health`, `/api/metrics`, `/docs`, `/openapi.json`, `/redoc`

**Default state:**
- `ORKESTRA_AUTH_ENABLED=false` in `docker-compose.yml` — ALL endpoints are unprotected in the default dev setup
- The default API key `test-orkestra-api-key` is public (committed to the repository)

**To enable auth:**
```bash
# In .env or docker-compose.yml:
ORKESTRA_AUTH_ENABLED=true
ORKESTRA_API_KEYS=your-secret-key-here
```

There is no role-based access control — all valid API keys have identical, full access.

#### Secret storage

Secrets (e.g., MCP tool API keys) are stored in the `Secret` table in PostgreSQL, encrypted with Fernet symmetric encryption (`app/services/secret_service.py`).

**Key management:**
- Key source: `ORKESTRA_FERNET_KEY` environment variable (base64-encoded Fernet key)
- In development: if `ORKESTRA_FERNET_KEY` is not set, an ephemeral key is generated at startup
- **Ephemeral key behavior**: all stored secrets become undecryptable on container restart
- In production: always set a stable `ORKESTRA_FERNET_KEY`

Generate a key:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### Code execution sandbox

When an agent has `allow_code_execution=True`, it can call the `execute_python_code` tool. Code runs in a Docker container using the `python:3.12-slim` image.

**Isolation mechanism:**
- Each code execution spawns a new container
- Container is destroyed after execution
- The host Docker daemon is accessible via `/var/run/docker.sock` (mounted in both `api` and `celery-worker` containers)

**Risks:**
- Mounting the Docker socket grants the container significant privileges over the host
- Code executed by agents is not sandboxed from the network unless Docker network policies are configured
- There is no enforced resource limit (CPU/memory) per code execution container

#### What is NOT guaranteed

These are current limitations that affect the security posture of the system:

1. **Governance forbidden_effects are not enforced at the API layer.** An agent configured with `forbidden_effects: ["external_write"]` receives a text constraint in its system prompt. The API does not block execution based on what tools the agent actually called.

2. **Approval workflows are not automatically triggered.** The approval API exists but is not wired to interrupt agent execution in real time.

3. **No input validation of agent output.** The API does not inspect or sanitize what an agent writes to its output. If an agent outputs malicious content, that content is stored and returned as-is.

4. **No audit of who holds an API key.** All valid keys have identical access; there is no per-key audit trail.

5. **Docker socket access is a high-privilege mount.** Both the api and celery-worker containers can create, start, and stop containers on the host Docker daemon. This is a significant privilege.

#### Reporting security issues

Open a GitHub issue labeled `security` in the repository. For sensitive disclosures, contact the repository owner directly via GitHub.

#### Default credentials to change before any deployment

| Setting | Default value | Action required |
|---------|--------------|----------------|
| `ORKESTRA_API_KEYS` | `test-orkestra-api-key` | Replace with a secret key |
| `ORKESTRA_SECRET_KEY` | `orkestra-dev-secret-key-change-in-production` | Replace with a random secret |
| `ORKESTRA_FERNET_KEY` | (auto-generated) | Set a stable Fernet key |
| `ORKESTRA_AUTH_ENABLED` | `false` (in compose) | Set to `true` |
| Grafana admin password | `orkestra` (in compose) | Change in production |
