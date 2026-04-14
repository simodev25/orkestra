#### Development setup

**Python backend:**
```bash
# Python 3.12 required
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `pyproject.toml` defines dev dependencies. If it does not exist, install from the project metadata.

**Frontend:**
```bash
cd frontend
npm install
npm run dev   # starts on http://localhost:3000
```

For frontend development against a running API:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8200 npm run dev
```

#### Running services locally (without Docker)

You need: PostgreSQL, Redis, and Ollama running. Set these env vars in `.env`:
```
ORKESTRA_DATABASE_URL=postgresql+asyncpg://orkestra:orkestra@localhost:5432/orkestra
ORKESTRA_DATABASE_URL_SYNC=postgresql://orkestra:orkestra@localhost:5432/orkestra
ORKESTRA_REDIS_URL=redis://localhost:6379/0
```

Run the API:
```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8200 --reload
```

Run the Celery worker:
```bash
celery -A app.celery_app:celery worker --loglevel=info --concurrency=2
```

#### Running the test suite

```bash
pytest tests/ -x -v --asyncio-mode=auto
```

Specific test file:
```bash
pytest tests/test_lab/test_assertion_engine.py -x -v
```

In the Docker container:
```bash
docker compose exec api pytest tests/ -x --asyncio-mode=auto
```

The tests use `asyncio_mode=auto` (configured in `pytest.ini` or `pyproject.toml`).

#### Database migrations

Create a new migration (after changing an ORM model):
```bash
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

Apply all pending migrations:
```bash
alembic upgrade head
```

Roll back one migration:
```bash
alembic downgrade -1
```

#### Code conventions

- **Python**: no specific formatter enforced; keep consistent with existing code style
- **No mock fallbacks**: do not add silent fallback to fake data — fail loudly or handle explicitly
- **Type hints**: use throughout new Python code
- **Docstrings**: not required for internal-only functions; document public API surface
- **Tests**: add tests for new services and routes; use `pytest-asyncio` for async tests
- **Migrations**: all schema changes must include an Alembic migration; the API auto-runs migrations on startup

#### Pull request checklist

Before opening a PR:
- [ ] Tests pass: `pytest tests/ -x --asyncio-mode=auto`
- [ ] If the DB schema changed: include an Alembic migration in `migrations/versions/`
- [ ] If a new env var was added: document it in `docs/configuration.md`
- [ ] If a new limitation was discovered: add it to `docs/limitations.md`
- [ ] No hardcoded secrets or API keys in new code

#### Project structure

```
app/
  api/routes/       FastAPI route handlers (thin — delegate to services)
  core/             Auth, config, database, logging, tracing
  models/           SQLAlchemy ORM models
  schemas/          Pydantic request/response schemas
  services/         Business logic
    test_lab/       Test Lab orchestration (16 files)
  state_machines/   Lifecycle state machines (agents, MCPs, cases)
  tasks/            Celery async tasks
  config/           Seed data (families.seed.json, skills.seed.json)
frontend/
  src/app/          Next.js App Router pages (~34 routes)
tests/              pytest test suite (44 files)
migrations/         Alembic migration scripts
docs/               Project documentation
observability/      OTel, Prometheus, Tempo, Grafana configs
```
