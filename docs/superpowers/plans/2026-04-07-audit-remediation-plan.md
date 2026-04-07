# Orkestra Audit Remediation -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 31 audit findings (F01-F31) across 4 phases to bring Orkestra from prototype (3/10) to production-ready MVP (7+/10).

**Architecture:** Remediation is organized in dependency order -- Phase 0 (critical blockers) unblocks Phase 1 (architecture stabilization), which unblocks Phase 2 (industrialization) and Phase 3 (scale-up). Each task is self-contained with a test-first approach.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, PostgreSQL 16, Redis 7, Celery, Next.js 14, TypeScript, React Query, Tailwind CSS

**Audit Reference:** `AUDIT_REPORT.md` at project root

---

## Phase 0 -- Critical Fixes (Findings F01-F04, F07, F18)

These are blockers that must be fixed before any other work.

---

### Task 1: Add Missing Test Lab Database Migration (F01)

**Files:**
- Create: `migrations/versions/010_test_lab_tables.py`
- Reference: `app/models/test_lab.py` (lines 12-90)
- Reference: `app/models/agent_test_run.py` (lines 12-27)

- [ ] **Step 1: Generate the migration skeleton**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
source .venv/bin/activate
alembic revision -m "add test lab and agent test run tables"
```

Expected: new file created in `migrations/versions/`

- [ ] **Step 2: Write the migration**

Replace the generated file content with:

```python
"""add test lab and agent test run tables

Revision ID: 010
Revises: 009_platform_secrets
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "010_test_lab_tables"
down_revision = "009_platform_secrets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agent_id", sa.String(100), nullable=False, index=True),
        sa.Column("input_prompt", sa.Text, nullable=True),
        sa.Column("input_payload", JSONB, nullable=True),
        sa.Column("allowed_tools", JSONB, nullable=True),
        sa.Column("expected_tools", JSONB, nullable=True),
        sa.Column("timeout_seconds", sa.Integer, default=120),
        sa.Column("max_iterations", sa.Integer, default=5),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("assertions", JSONB, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), nullable=True, index=True),
        sa.Column("agent_id", sa.String(100), nullable=False, index=True),
        sa.Column("agent_version", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), default="queued"),
        sa.Column("verdict", sa.String(30), nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("final_output", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("execution_metadata", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "test_run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("phase", sa.String(30), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "test_run_assertions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("assertion_type", sa.String(50), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("expected", sa.Text, nullable=True),
        sa.Column("actual", sa.Text, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("critical", sa.Boolean, default=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "test_run_diagnostics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("probable_causes", JSONB, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "agent_test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(100), nullable=False, index=True),
        sa.Column("agent_version", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("verdict", sa.String(20), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("raw_output", sa.Text, nullable=True),
        sa.Column("task", sa.Text, nullable=True),
        sa.Column("token_usage", sa.JSON, nullable=True),
        sa.Column("behavioral_checks", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("trace_data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Add indexes for common query patterns
    op.create_index("ix_test_runs_status", "test_runs", ["status"])
    op.create_index("ix_test_run_events_event_type", "test_run_events", ["event_type"])
    op.create_index("ix_agent_test_runs_status", "agent_test_runs", ["status"])
    op.create_index("ix_agent_test_runs_created_at", "agent_test_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_test_runs")
    op.drop_table("test_run_diagnostics")
    op.drop_table("test_run_assertions")
    op.drop_table("test_run_events")
    op.drop_table("test_runs")
    op.drop_table("test_scenarios")
```

- [ ] **Step 3: Verify migration applies cleanly**

```bash
# Requires running PostgreSQL (docker compose up -d postgres)
alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade 009_platform_secrets -> 010_test_lab_tables`

- [ ] **Step 4: Verify downgrade works**

```bash
alembic downgrade -1
alembic upgrade head
```

Expected: clean downgrade and re-upgrade with no errors.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/010_test_lab_tables.py
git commit -m "fix(F01): add missing migration for 6 test lab tables"
```

---

### Task 2: Add Authentication Middleware (F02, F04)

**Files:**
- Create: `app/core/auth.py`
- Modify: `app/core/config.py:8-51` (add auth config fields)
- Modify: `app/api/deps.py` (add auth dependency)
- Modify: `app/main.py:56-62` (add auth middleware)
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing test for API key authentication**

Create `tests/test_auth.py`:

```python
"""Tests for API key authentication middleware."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def authed_headers():
    return {"X-API-Key": "test-orkestra-api-key"}


@pytest.fixture
def no_auth_headers():
    return {}


@pytest.mark.asyncio
async def test_health_is_public():
    """Health endpoint should work without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_agents_requires_auth():
    """Protected endpoints should return 401 without API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing or invalid API key"


@pytest.mark.asyncio
async def test_agents_with_valid_key():
    """Protected endpoints should work with valid API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/agents",
            headers={"X-API-Key": "test-orkestra-api-key"},
        )
    # Should not be 401 (may be 200 or other depending on DB state)
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_agents_with_invalid_key():
    """Protected endpoints should reject invalid API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/agents",
            headers={"X-API-Key": "wrong-key"},
        )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py -v
```

Expected: FAIL -- `test_agents_requires_auth` will pass as 200 (no auth enforcement yet).

- [ ] **Step 3: Add auth config fields to Settings**

In `app/core/config.py`, add after the `SECRET_KEY` field (around line 17):

```python
    # Authentication
    API_KEYS: str = "test-orkestra-api-key"  # comma-separated list of valid API keys
    AUTH_ENABLED: bool = True
    PUBLIC_PATHS: str = "/api/health,/api/metrics,/docs,/openapi.json,/redoc"
```

- [ ] **Step 4: Create auth module**

Create `app/core/auth.py`:

```python
"""API Key authentication for Orkestra."""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API key authentication on non-public paths."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()

        if not settings.AUTH_ENABLED:
            return await call_next(request)

        # Allow CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check if path is public
        public_paths = [p.strip() for p in settings.PUBLIC_PATHS.split(",")]
        path = request.url.path
        if any(path.startswith(pp) for pp in public_paths):
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-API-Key")
        valid_keys = [k.strip() for k in settings.API_KEYS.split(",")]

        if not api_key or api_key not in valid_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid API key",
            )

        return await call_next(request)
```

- [ ] **Step 5: Wire auth middleware into the app**

In `app/main.py`, add import at the top:

```python
from app.core.auth import ApiKeyMiddleware
```

Add the middleware **before** the CORS middleware (around line 55, before the CORSMiddleware add):

```python
    app.add_middleware(ApiKeyMiddleware)
```

- [ ] **Step 6: Update deps.py to expose an auth dependency for routes that need user context**

Replace `app/api/deps.py` content:

```python
"""Shared FastAPI dependencies."""
from app.core.database import get_db

__all__ = ["get_db"]
```

No change needed here yet -- the middleware handles auth globally. User context injection comes in Phase 2 (RBAC).

- [ ] **Step 7: Run tests to verify auth works**

```bash
pytest tests/test_auth.py -v
```

Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add app/core/auth.py app/core/config.py app/api/deps.py app/main.py tests/test_auth.py
git commit -m "fix(F02,F04): add API key authentication middleware"
```

---

### Task 3: Encrypt Platform Secrets (F03)

**Files:**
- Modify: `app/models/secret.py` (add encryption/decryption)
- Modify: `app/core/config.py` (add FERNET_KEY)
- Create: `app/core/encryption.py`
- Modify: `app/api/routes/settings.py` (decrypt on read, encrypt on write)
- Create: `tests/test_encryption.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_encryption.py`:

```python
"""Tests for secret encryption."""
import pytest


def test_encrypt_decrypt_roundtrip():
    from app.core.encryption import encrypt_value, decrypt_value
    plaintext = "sk-my-secret-api-key-12345"
    encrypted = encrypt_value(plaintext)
    assert encrypted != plaintext
    assert decrypt_value(encrypted) == plaintext


def test_encrypt_produces_different_ciphertexts():
    from app.core.encryption import encrypt_value
    a = encrypt_value("same-value")
    b = encrypt_value("same-value")
    # Fernet uses random IV so ciphertexts differ
    assert a != b


def test_decrypt_invalid_raises():
    from app.core.encryption import decrypt_value
    with pytest.raises(Exception):
        decrypt_value("not-valid-fernet-token")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_encryption.py -v
```

Expected: FAIL -- `ModuleNotFoundError: No module named 'app.core.encryption'`

- [ ] **Step 3: Add Fernet key to config**

In `app/core/config.py`, add to the Settings class (after SECRET_KEY):

```python
    FERNET_KEY: str = ""  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- [ ] **Step 4: Add cryptography dependency**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra
pip install cryptography
```

Add `"cryptography>=43.0.0"` to `pyproject.toml` dependencies list.

- [ ] **Step 5: Create encryption module**

Create `app/core/encryption.py`:

```python
"""Fernet encryption for platform secrets."""
from cryptography.fernet import Fernet
from app.core.config import get_settings

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        settings = get_settings()
        key = settings.FERNET_KEY
        if not key:
            # Auto-generate a key for dev (NOT for production)
            key = Fernet.generate_key().decode()
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string, return base64 Fernet token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet token, return plaintext string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 6: Run encryption tests**

```bash
pytest tests/test_encryption.py -v
```

Expected: ALL PASS

- [ ] **Step 7: Update settings routes to encrypt on write, mask on read**

In `app/api/routes/settings.py`, in the `upsert_secret` handler, wrap the value:

```python
from app.core.encryption import encrypt_value, decrypt_value
```

Before persisting `secret.value = payload.value`, change to:
```python
secret.value = encrypt_value(payload.value)
```

In `list_secrets`, the masking already exists (`value[: 4] + "****"`). Leave as-is -- decryption is only needed when actually using the secret (in services).

- [ ] **Step 8: Commit**

```bash
git add app/core/encryption.py app/core/config.py app/api/routes/settings.py tests/test_encryption.py pyproject.toml
git commit -m "fix(F03): encrypt platform secrets with Fernet"
```

---

### Task 4: Remove Silent Simulation Fallbacks (F07)

**Files:**
- Modify: `app/services/mcp_executor.py:112-126`
- Modify: `app/services/subagent_executor.py:69-91`

- [ ] **Step 1: Fix mcp_executor -- fail explicitly instead of simulating**

In `app/services/mcp_executor.py`, replace the `except Exception` block (around lines 112-126):

**Old code:**
```python
    except Exception:
        pass

    # Fallback: simulated execution
    inv.status = "completed"
    inv.latency_ms = 120
    inv.cost = 0.02
    inv.output_summary = f"MCP {mcp_id} completed (simulated)"
```

**New code:**
```python
    except Exception as exc:
        inv.status = "failed"
        inv.latency_ms = 0
        inv.cost = 0.0
        inv.output_summary = f"MCP {mcp_id} execution failed: {exc}"
        inv.ended_at = datetime.now(timezone.utc)

        await emit_event(db, "mcp.failed", "runtime", "mcp_executor",
                         run_id=run_id,
                         payload={"mcp_id": mcp_id, "error": str(exc)})

        await db.flush()
        return inv
```

- [ ] **Step 2: Fix subagent_executor -- fail explicitly instead of simulating**

In `app/services/subagent_executor.py`, replace the `except Exception` block (around lines 69-91):

**Old code:**
```python
    except Exception:
        pass

    # Fallback: simulated execution
    invocation.status = "completed"
    invocation.confidence_score = 0.85
    invocation.output_summary = f"Agent {agent_id} completed successfully (simulated)"
```

**New code:**
```python
    except Exception as exc:
        invocation.status = "failed"
        invocation.confidence_score = 0.0
        invocation.output_summary = f"Agent {agent_id} execution failed: {exc}"
        invocation.cost = 0.0
        invocation.ended_at = datetime.now(timezone.utc)
        invocation.result_payload = {
            "agent_id": agent_id,
            "status": "failed",
            "error": str(exc),
        }

        await emit_event(db, "agent.failed", "runtime", "subagent_executor",
                         run_id=run_id,
                         payload={"agent_id": agent_id, "error": str(exc)})

        await db.flush()
        return invocation
```

- [ ] **Step 3: Run existing executor tests**

```bash
pytest tests/test_executors.py -v
```

Expected: Tests may need updating since they might expect "completed" status from simulation. Update assertions to expect "failed" if the mock LLM is not available.

- [ ] **Step 4: Commit**

```bash
git add app/services/mcp_executor.py app/services/subagent_executor.py
git commit -m "fix(F07): remove silent simulation fallbacks, fail explicitly on execution errors"
```

---

### Task 5: Fix msg_count NameError Bug (F18)

**Files:**
- Modify: `app/services/test_lab/orchestrator.py:469`

- [ ] **Step 1: Fix the undefined variable**

In `app/services/test_lab/orchestrator.py`, at line 469, replace:

```python
"iteration_count": msg_count,
```

with:

```python
"iteration_count": len(message_history),
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/orchestrator.py
git commit -m "fix(F18): replace undefined msg_count with len(message_history)"
```

---

### Task 6: Restrict CORS Origins (F02 supplement)

**Files:**
- Modify: `app/main.py:56-62`
- Modify: `app/core/config.py`

- [ ] **Step 1: Add configurable CORS origins to Settings**

In `app/core/config.py`, add to Settings:

```python
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3300,http://localhost:5173"
```

- [ ] **Step 2: Update CORS middleware in main.py**

In `app/main.py`, replace the CORS middleware block:

**Old:**
```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3300", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

**New:**
```python
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py app/core/config.py
git commit -m "fix(F02): restrict CORS to specific methods and headers"
```

---

### Task 7: Remove Frontend Mock Fallbacks (F08)

**Files:**
- Modify: `frontend/src/lib/mcp/service.ts` (remove MOCK_MCPS fallback)
- Modify: `frontend/src/lib/agent-test-lab/mock-runner.ts` (remove trivial checks)

- [ ] **Step 1: Fix MCP service -- throw errors instead of returning mock data**

In `frontend/src/lib/mcp/service.ts`, for each function that catches and returns `MOCK_MCPS`, change the catch block to rethrow:

For `listMcps`:
```typescript
// OLD: catch () { return MOCK_MCPS; }
// NEW:
catch (err) {
  console.error("Failed to list MCPs:", err);
  throw err;
}
```

Apply the same pattern to: `getMcp`, `getCatalogStats`, `getMcpHealth`, `getMcpUsage`, `testMcp`, `listAgentIds`.

- [ ] **Step 2: Fix behavioral checks -- remove trivially-true checks**

In `frontend/src/lib/agent-test-lab/mock-runner.ts`, update `evaluateCheck`:

```typescript
function evaluateCheck(key: string, output: string): boolean {
  const hasContent = output.trim().length > 20;
  switch (key) {
    case "stayInScope":
      return !output.toLowerCase().includes("not within my scope") &&
             !output.toLowerCase().includes("cannot help with");
    case "structuredOutput":
      return output.includes("{") || output.includes("- ") ||
             output.includes("##") || output.includes("1.");
    case "groundedEvidence":
      return hasContent;
    case "avoidsHallucination":
      return hasContent;
    // These checks cannot be evaluated client-side -- skip them
    case "flagsMissingData":
    case "handlesAmbiguity":
    case "refusesOutOfScopeAction":
      return false; // Mark as NOT EVALUATED instead of always true
    default:
      return false;
  }
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
git add src/lib/mcp/service.ts src/lib/agent-test-lab/mock-runner.ts
git commit -m "fix(F06,F08): remove mock fallbacks and trivially-true behavioral checks"
```

---

### Task 8: Fix Dead Sidebar Links (F19)

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx:10-30`

- [ ] **Step 1: Remove links to non-existent pages**

In `frontend/src/components/layout/sidebar.tsx`, remove or comment out these nav entries that point to unimplemented pages:

Remove from the NAV array:
- `{ label: "Requests", href: "/requests", ... }`
- `{ label: "Cases", href: "/cases", ... }`
- `{ label: "Plans", href: "/plans", ... }`
- `{ label: "Runs", href: "/runs", ... }`
- `{ label: "Control", href: "/control", ... }`
- `{ label: "Approvals", href: "/approvals", ... }`
- `{ label: "Audit", href: "/audit", ... }`
- `{ label: "Workflows", href: "/workflows", ... }`
- `{ label: "Admin", href: "/admin", ... }`

Keep only:
- Dashboard `/`
- Agents `/agents`
- Families `/agents/families`
- Agent Skills `/agents/skills`
- Test Lab `/test-lab`
- MCP Catalog `/mcps`

Remove the "Operations", "Governance", "Configuration" section headers if empty.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/sidebar.tsx
git commit -m "fix(F19): remove sidebar links to unimplemented pages"
```

---

## Phase 1 -- Architecture Stabilization (Findings F05, F09, F10, F14-F17, F20-F24, F26-F27)

---

### Task 9: Fix DateTime Type Hints (F14)

**Files:**
- Modify: `app/models/run.py:19-20,39-40`
- Modify: `app/models/audit.py:18`
- Modify: `app/models/invocation.py` (same pattern)
- Modify: `app/models/approval.py` (same pattern)

- [ ] **Step 1: Fix Run model**

In `app/models/run.py`, change:

```python
# OLD
started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), ...)
ended_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), ...)
```

to:

```python
from datetime import datetime
# NEW
started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), ...)
ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), ...)
```

Apply to both `Run` (lines 19-20) and `RunNode` (lines 39-40).

- [ ] **Step 2: Fix AuditEvent model**

In `app/models/audit.py`, line 18, change:

```python
# OLD
timestamp: Mapped[str] = mapped_column(DateTime(timezone=True), default=utcnow)
# NEW
timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 3: Fix SubagentInvocation and MCPInvocation models**

In `app/models/invocation.py`, fix all `Mapped[str | None]` on DateTime columns to `Mapped[datetime | None]`.

- [ ] **Step 4: Fix ApprovalRequest model**

In `app/models/approval.py`, same pattern.

- [ ] **Step 5: Run tests**

```bash
pytest tests/ -v --tb=short
```

Expected: ALL PASS (type hints don't affect runtime behavior with SQLAlchemy).

- [ ] **Step 6: Commit**

```bash
git add app/models/run.py app/models/audit.py app/models/invocation.py app/models/approval.py
git commit -m "fix(F14): correct Mapped[str] to Mapped[datetime] on DateTime columns"
```

---

### Task 10: Fix ID Prefix Collision and Entropy (F15, F16)

**Files:**
- Modify: `app/models/test_lab.py:52` (change `evt_` to `tevt_`)
- Modify: `app/models/base.py:16-19` (increase `new_id` entropy)

- [ ] **Step 1: Fix prefix collision -- TestRunEvent**

In `app/models/test_lab.py`, line 52, change:

```python
# OLD
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("evt_"))
# NEW
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("tevt_"))
```

- [ ] **Step 2: Increase new_id entropy**

In `app/models/base.py`, line 17-18, change:

```python
# OLD
uid = uuid.uuid4().hex[:12]
# NEW
uid = uuid.uuid4().hex  # Full 32 hex chars = 128 bits entropy
```

- [ ] **Step 3: Commit**

```bash
git add app/models/test_lab.py app/models/base.py
git commit -m "fix(F15,F16): unique prefix for TestRunEvent, full UUID entropy in new_id"
```

---

### Task 11: Add Foreign Key Constraints on Operational Tables (F09)

**Files:**
- Create: `migrations/versions/011_add_foreign_keys.py`

- [ ] **Step 1: Generate migration**

```bash
alembic revision -m "add foreign key constraints on operational tables"
```

- [ ] **Step 2: Write the migration**

```python
"""add foreign key constraints on operational tables

Revision ID: 011
Revises: 010_test_lab_tables
"""
from alembic import op

revision = "011_add_foreign_keys"
down_revision = "010_test_lab_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cases -> Requests
    op.create_foreign_key("fk_cases_request_id", "cases", "requests",
                          ["request_id"], ["id"], ondelete="SET NULL")

    # Runs -> Cases
    op.create_foreign_key("fk_runs_case_id", "runs", "cases",
                          ["case_id"], ["id"], ondelete="CASCADE")

    # RunNodes -> Runs
    op.create_foreign_key("fk_run_nodes_run_id", "run_nodes", "runs",
                          ["run_id"], ["id"], ondelete="CASCADE")

    # SubagentInvocations -> RunNodes
    op.create_foreign_key("fk_subagent_inv_run_node_id", "subagent_invocations", "run_nodes",
                          ["run_node_id"], ["id"], ondelete="CASCADE")

    # MCPInvocations -> SubagentInvocations
    op.create_foreign_key("fk_mcp_inv_subagent_id", "mcp_invocations", "subagent_invocations",
                          ["subagent_invocation_id"], ["id"], ondelete="CASCADE")

    # AuditEvents -> Runs (nullable)
    op.create_foreign_key("fk_audit_events_run_id", "audit_events", "runs",
                          ["run_id"], ["id"], ondelete="SET NULL")

    # TestRuns -> TestScenarios
    op.create_foreign_key("fk_test_runs_scenario_id", "test_runs", "test_scenarios",
                          ["scenario_id"], ["id"], ondelete="SET NULL")

    # TestRuns -> AgentDefinitions
    op.create_foreign_key("fk_test_runs_agent_id", "test_runs", "agent_definitions",
                          ["agent_id"], ["id"], ondelete="CASCADE")

    # TestRunEvents -> TestRuns
    op.create_foreign_key("fk_test_run_events_run_id", "test_run_events", "test_runs",
                          ["run_id"], ["id"], ondelete="CASCADE")

    # TestRunAssertions -> TestRuns
    op.create_foreign_key("fk_test_run_assertions_run_id", "test_run_assertions", "test_runs",
                          ["run_id"], ["id"], ondelete="CASCADE")

    # TestRunDiagnostics -> TestRuns
    op.create_foreign_key("fk_test_run_diagnostics_run_id", "test_run_diagnostics", "test_runs",
                          ["run_id"], ["id"], ondelete="CASCADE")

    # AgentTestRuns -> AgentDefinitions
    op.create_foreign_key("fk_agent_test_runs_agent_id", "agent_test_runs", "agent_definitions",
                          ["agent_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_agent_test_runs_agent_id", "agent_test_runs", type_="foreignkey")
    op.drop_constraint("fk_test_run_diagnostics_run_id", "test_run_diagnostics", type_="foreignkey")
    op.drop_constraint("fk_test_run_assertions_run_id", "test_run_assertions", type_="foreignkey")
    op.drop_constraint("fk_test_run_events_run_id", "test_run_events", type_="foreignkey")
    op.drop_constraint("fk_test_runs_agent_id", "test_runs", type_="foreignkey")
    op.drop_constraint("fk_test_runs_scenario_id", "test_runs", type_="foreignkey")
    op.drop_constraint("fk_audit_events_run_id", "audit_events", type_="foreignkey")
    op.drop_constraint("fk_mcp_inv_subagent_id", "mcp_invocations", type_="foreignkey")
    op.drop_constraint("fk_subagent_inv_run_node_id", "subagent_invocations", type_="foreignkey")
    op.drop_constraint("fk_run_nodes_run_id", "run_nodes", type_="foreignkey")
    op.drop_constraint("fk_runs_case_id", "runs", type_="foreignkey")
    op.drop_constraint("fk_cases_request_id", "cases", type_="foreignkey")
```

- [ ] **Step 3: Apply migration**

```bash
alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/011_add_foreign_keys.py
git commit -m "fix(F09): add foreign key constraints on operational tables"
```

---

### Task 12: Extract run_agent_test Business Logic to Service (F10)

**Files:**
- Create: `app/services/agent_test_run_service.py`
- Modify: `app/api/routes/agents.py:238-461`
- Create: `tests/test_agent_test_run_service.py`

- [ ] **Step 1: Create the service module**

Create `app/services/agent_test_run_service.py`:

```python
"""Service for agent test run execution, persistence, and debug tracing."""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent_test_run import AgentTestRun
from app.models.registry import AgentDefinition
from app.services.agent_test_service import execute_test_run
from app.services.prompt_builder import build_agent_prompt
from app.services import agent_registry_service
from app.core.config import get_settings


async def run_test(
    db: AsyncSession,
    agent: AgentDefinition,
    task: str,
    structured_input: dict | None = None,
    evidence: str | None = None,
    context_variables: dict | None = None,
) -> dict:
    """Execute a test run against an agent and persist results.

    Returns a dict with test run ID, results, and debug file path.
    """
    result = await execute_test_run(
        db, agent, task, structured_input, evidence, context_variables,
    )

    # Build trace metadata
    trace_meta = _build_trace_meta(agent)

    # Persist the test run
    test_run = AgentTestRun(
        agent_id=agent.id,
        agent_version=agent.version,
        status=result.get("status", "completed"),
        verdict=result.get("verdict", "unknown"),
        latency_ms=result.get("latency_ms"),
        provider=result.get("provider"),
        model=result.get("model"),
        raw_output=result.get("raw_output", ""),
        task=task,
        token_usage=result.get("token_usage"),
        behavioral_checks=result.get("behavioral_checks"),
        error_message=result.get("error"),
        trace_data=trace_meta,
    )
    db.add(test_run)
    await db.flush()

    # Save debug file
    debug_file = _save_debug_file(agent, test_run, result, trace_meta, task)

    return {
        "id": test_run.id,
        "agent_id": agent.id,
        "agent_version": agent.version,
        "created_at": test_run.created_at.isoformat() if test_run.created_at else None,
        "debug_file": debug_file,
        **result,
    }


async def list_runs(db: AsyncSession, agent_id: str, limit: int = 50) -> list[dict]:
    """List recent test runs for an agent."""
    stmt = (
        select(AgentTestRun)
        .where(AgentTestRun.agent_id == agent_id)
        .order_by(AgentTestRun.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "agent_version": r.agent_version,
            "status": r.status,
            "verdict": r.verdict,
            "latency_ms": r.latency_ms,
            "provider": r.provider,
            "model": r.model,
            "task": r.task,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _build_trace_meta(agent: AgentDefinition) -> dict:
    """Build trace metadata from agent definition."""
    skills = []
    if hasattr(agent, "agent_skills") and agent.agent_skills:
        skills = [{"skill_id": ask.skill_id} for ask in agent.agent_skills]

    return {
        "agent_id": agent.id,
        "agent_version": agent.version,
        "family_id": agent.family_id,
        "skills": skills,
        "allowed_mcps": agent.allowed_mcps or [],
        "forbidden_effects": agent.forbidden_effects or [],
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
    }


def _save_debug_file(
    agent: AgentDefinition,
    test_run: AgentTestRun,
    result: dict,
    trace_meta: dict,
    task: str,
) -> str | None:
    """Save debug JSON file and return filename."""
    settings = get_settings()
    debug_dir = settings.DEBUG_STRATEGY_DIR
    if not debug_dir:
        return None

    debug_path = Path(debug_dir)
    debug_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{agent.id}_test_{result.get('verdict', 'unknown')}_{agent.version}_{ts}.json"

    payload = {
        "test_run_id": test_run.id,
        "agent_id": agent.id,
        "task": task,
        "result": result,
        "trace": trace_meta,
    }

    (debug_path / filename).write_text(json.dumps(payload, indent=2, default=str))
    return filename
```

- [ ] **Step 2: Simplify the route handler**

In `app/api/routes/agents.py`, replace the `run_agent_test` handler (lines 238-423) with:

```python
from app.services import agent_test_run_service

@router.post("/{agent_id}/test-run")
async def run_agent_test(agent_id: str, body: TestRunRequest, db: AsyncSession = Depends(get_db)):
    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    try:
        result = await agent_test_run_service.run_test(
            db, agent, body.task,
            structured_input=body.structured_input,
            evidence=body.evidence,
            context_variables=body.context_variables,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

Replace the `list_agent_test_runs` handler similarly:

```python
@router.get("/{agent_id}/test-runs")
async def list_agent_test_runs(agent_id: str, db: AsyncSession = Depends(get_db)):
    return await agent_test_run_service.list_runs(db, agent_id)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_api_agents.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/services/agent_test_run_service.py app/api/routes/agents.py
git commit -m "refactor(F10): extract agent test run logic from route to service"
```

---

### Task 13: Fix Duplicated Query in _sync_agent_skills (F21)

**Files:**
- Modify: `app/services/agent_registry_service.py:126-128`

- [ ] **Step 1: Remove the dead query**

In `app/services/agent_registry_service.py`, around lines 124-139, remove the first useless query:

```python
async def _sync_agent_skills(db: AsyncSession, agent_id: str, skill_ids: list[str]) -> None:
    """Replace agent's AgentSkill rows with the given skill_ids list."""
    # Delete existing entries
    existing_result = await db.execute(
        select(AgentSkill).where(AgentSkill.agent_id == agent_id)
    )
    for row in existing_result.scalars().all():
        await db.delete(row)
    # ... rest unchanged
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_api_agents.py tests/test_api_agent_registry_product.py -v
```

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_registry_service.py
git commit -m "fix(F21): remove duplicated dead query in _sync_agent_skills"
```

---

### Task 14: Remove Operational Fields from AgentCreate Schema (F26)

**Files:**
- Modify: `app/schemas/agent.py:15-42`

- [ ] **Step 1: Remove client-settable operational fields**

In `app/schemas/agent.py`, remove these fields from `AgentCreate`:

```python
    # REMOVE these three lines:
    last_test_status: str = "not_tested"
    last_validated_at: Optional[str] = None
    usage_count: int = 0
```

These fields should be computed server-side only, not settable via the create API.

- [ ] **Step 2: Set defaults in the service layer**

In `app/services/agent_registry_service.py`, in `create_agent()`, ensure these fields get default values:

```python
agent = AgentDefinition(
    **data.model_dump(exclude_unset=True),
    last_test_status="not_tested",
    last_validated_at=None,
    usage_count=0,
)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_api_agents.py tests/test_api_agent_registry_product.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/schemas/agent.py app/services/agent_registry_service.py
git commit -m "fix(F26): remove operational fields from AgentCreate schema"
```

---

### Task 15: Add Enum Validation on Status Fields (F27)

**Files:**
- Modify: `app/models/enums.py` (add FamilyStatus, SkillStatus)
- Modify: `app/schemas/agent.py` (use AgentStatus enum)
- Modify: `app/schemas/family.py` (use FamilyStatus enum)
- Modify: `app/schemas/skill.py` (use SkillStatus enum)

- [ ] **Step 1: Add missing enums**

In `app/models/enums.py`, add:

```python
class FamilyStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deprecated = "deprecated"


class SkillStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deprecated = "deprecated"
```

- [ ] **Step 2: Use enums in schemas**

In `app/schemas/agent.py`, change `status` fields to use enum:

```python
from app.models.enums import AgentStatus, Criticality, CostProfile

class AgentCreate(OrkBaseSchema):
    # ...
    criticality: Criticality = Criticality.MEDIUM
    cost_profile: CostProfile = CostProfile.MEDIUM
    status: AgentStatus = AgentStatus.DRAFT
```

In `app/schemas/family.py`:
```python
from app.models.enums import FamilyStatus

class FamilyCreate(OrkBaseSchema):
    status: FamilyStatus = FamilyStatus.active
```

In `app/schemas/skill.py`:
```python
from app.models.enums import SkillStatus

class SkillCreate(OrkBaseSchema):
    status: SkillStatus = SkillStatus.active
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 4: Commit**

```bash
git add app/models/enums.py app/schemas/agent.py app/schemas/family.py app/schemas/skill.py
git commit -m "fix(F27): add enum validation on status, criticality, cost_profile fields"
```

---

### Task 16: Add selectinload to Eliminate N+1 Queries (F24)

**Files:**
- Modify: `app/services/agent_registry_service.py` (list_agents query)
- Modify: `app/services/skill_service.py` (list_skills query)

- [ ] **Step 1: Fix agent listing N+1**

In `app/services/agent_registry_service.py`, in the `list_agents` function, add `selectinload` to the base query:

```python
from sqlalchemy.orm import selectinload

# In list_agents, change the base query:
stmt = select(AgentDefinition).options(
    selectinload(AgentDefinition.family_rel),
    selectinload(AgentDefinition.agent_skills),
)
```

- [ ] **Step 2: Fix skill listing N+1**

In `app/services/skill_service.py`, for any function that lists skills and resolves families, add selectinload similarly.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_api_agents.py tests/test_api_skills.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/services/agent_registry_service.py app/services/skill_service.py
git commit -m "perf(F24): add selectinload to eliminate N+1 queries on agent/skill listing"
```

---

### Task 17: Add Pagination to All List Endpoints (F23)

**Files:**
- Create: `app/schemas/pagination.py`
- Modify: `app/api/routes/agents.py` (add pagination params)
- Modify: `app/api/routes/families.py`
- Modify: `app/api/routes/skills.py`
- Modify: `app/api/routes/test_lab.py`
- Modify: `app/api/routes/mcp_catalog.py`
- Modify: `app/api/routes/mcps.py`

- [ ] **Step 1: Create shared pagination schema**

Create `app/schemas/pagination.py`:

```python
"""Shared pagination schema for list endpoints."""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List

T = TypeVar("T")


class PaginationParams(BaseModel):
    offset: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=50, ge=1, le=200, description="Max items to return")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    offset: int
    limit: int
    has_more: bool
```

- [ ] **Step 2: Apply pagination to agents list endpoint**

In `app/api/routes/agents.py`, update `list_agents`:

```python
from app.schemas.pagination import PaginationParams

@router.get("")
async def list_agents(
    offset: int = 0,
    limit: int = 50,
    # ... existing query params ...
    db: AsyncSession = Depends(get_db),
):
    agents, total = await agent_registry_service.list_agents(
        db, offset=offset, limit=limit, ...
    )
    return {
        "items": agents,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
    }
```

Update `agent_registry_service.list_agents` to also return total count:

```python
async def list_agents(db, *, offset=0, limit=50, **filters) -> tuple[list, int]:
    # ... build query ...
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar() or 0
    rows = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return rows, total
```

- [ ] **Step 3: Apply same pattern to families, skills, test_lab scenarios, mcps, mcp-catalog**

Each list endpoint gets `offset` and `limit` query params and returns `{items, total, offset, limit, has_more}`.

- [ ] **Step 4: Run tests**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add app/schemas/pagination.py app/api/routes/ app/services/
git commit -m "feat(F23): add pagination to all list endpoints"
```

---

### Task 18: Unify Frontend API Client (F20, F22)

**Files:**
- Create: `frontend/src/lib/api-client.ts`
- Modify: `frontend/src/lib/agent-registry/service.ts`
- Modify: `frontend/src/lib/families/service.ts`
- Modify: `frontend/src/lib/mcp-catalog/service.ts`
- Modify: `frontend/src/lib/mcp/service.ts`
- Modify: `frontend/src/lib/test-lab/api.ts`

- [ ] **Step 1: Create unified API client**

Create `frontend/src/lib/api-client.ts`:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8200";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // Add API key from localStorage or env
  const apiKey = typeof window !== "undefined"
    ? localStorage.getItem("orkestra_api_key") || ""
    : "";
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const resp = await fetch(url, { ...options, headers });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body.detail || resp.statusText);
  }

  if (resp.status === 204) return undefined as T;
  return resp.json();
}
```

- [ ] **Step 2: Refactor each domain service to use apiRequest**

In each of the 5 service files, replace the local `request<R>()` function with an import:

```typescript
import { apiRequest } from "../api-client";

// Replace all request<T>("/api/...") calls with apiRequest<T>("/api/...")
```

- [ ] **Step 3: Remove duplicate type definitions**

Decide on canonical types -- use the `agent-registry/types.ts` versions as source of truth. Remove the duplicates from `lib/types.ts` or make `lib/types.ts` re-export from domain modules.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/
git commit -m "refactor(F20,F22): unify API client, remove 5 duplicate request() helpers"
```

---

### Task 19: Fix Celery Worker Engine Creation Per Event (F17)

**Files:**
- Modify: `app/services/test_lab/orchestrator.py:35-76`

- [ ] **Step 1: Create a shared sync engine at module level**

In `app/services/test_lab/orchestrator.py`, replace the per-call engine creation:

```python
# At module level, after imports:
from app.core.config import get_settings

_sync_engine = None

def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        sync_url = settings.DATABASE_URL_SYNC
        if not sync_url:
            sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
        from sqlalchemy import create_engine
        _sync_engine = create_engine(sync_url, pool_size=5, max_overflow=3)
    return _sync_engine


def emit(run_id, event_type, phase, message, details=None, duration_ms=None):
    """Persist a test run event using the shared sync engine."""
    from sqlalchemy import text
    engine = _get_sync_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO test_run_events (id, run_id, event_type, phase, message, details, timestamp, duration_ms, created_at, updated_at)
            VALUES (:id, :run_id, :event_type, :phase, :message, :details, :ts, :duration_ms, :ts, :ts)
        """), {
            "id": new_id("tevt_"),
            "run_id": run_id,
            "event_type": event_type,
            "phase": phase,
            "message": message,
            "details": json.dumps(details) if details else None,
            "ts": datetime.now(timezone.utc),
            "duration_ms": duration_ms,
        })
        conn.commit()
```

Apply the same pattern to `update_run()`.

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/orchestrator.py
git commit -m "perf(F17): use shared sync engine in Celery worker instead of per-call creation"
```

---

### Task 20: Consolidate Triple MCP Mapping (Phase 1 architecture)

**Files:**
- Create: `app/services/mcp_tool_registry.py`
- Modify: `app/services/agent_factory.py` (use registry)
- Modify: `app/services/mcp_executor.py` (use registry)

- [ ] **Step 1: Create unified MCP tool registry**

Create `app/services/mcp_tool_registry.py`:

```python
"""Single source of truth for MCP tool resolution."""
import logging

logger = logging.getLogger(__name__)

_LOCAL_TOOLS: dict | None = None


def get_local_tools() -> dict:
    """Return mapping of MCP ID -> list of tool functions.

    This is the ONLY place local MCP tools are registered.
    """
    global _LOCAL_TOOLS
    if _LOCAL_TOOLS is not None:
        return _LOCAL_TOOLS

    _LOCAL_TOOLS = {}

    try:
        from app.mcp_servers.document_parser import parse_document, classify_document
        _LOCAL_TOOLS["document_parser"] = [parse_document, classify_document]
    except ImportError:
        logger.warning("document_parser tools not available")

    try:
        from app.mcp_servers.consistency_checker import check_consistency, validate_fields
        _LOCAL_TOOLS["consistency_checker"] = [check_consistency, validate_fields]
    except ImportError:
        logger.warning("consistency_checker tools not available")

    try:
        from app.mcp_servers.search_engine import search_knowledge
        _LOCAL_TOOLS["search_engine"] = [search_knowledge]
    except ImportError:
        logger.warning("search_engine tools not available")

    try:
        from app.mcp_servers.weather import get_weather
        _LOCAL_TOOLS["weather"] = [get_weather]
    except ImportError:
        logger.warning("weather tools not available")

    return _LOCAL_TOOLS


def get_tools_for_mcp(mcp_id: str) -> list | None:
    """Get tool functions for a given MCP ID, or None if not found locally."""
    return get_local_tools().get(mcp_id)
```

- [ ] **Step 2: Update agent_factory.py to use the registry**

Replace the inline `MCP_TOOL_MAP` building in `get_tools_for_agent()` with:

```python
from app.services.mcp_tool_registry import get_tools_for_mcp

# In get_tools_for_agent():
for mcp_id in allowed_mcps:
    tools = get_tools_for_mcp(mcp_id)
    if tools:
        all_tools.extend(tools)
```

- [ ] **Step 3: Update mcp_executor.py to use the registry**

Replace the `_get_mcp_tools()` function with:

```python
from app.services.mcp_tool_registry import get_tools_for_mcp

# In _execute_mcp_tool():
tools = get_tools_for_mcp(mcp_id)
if not tools:
    raise ValueError(f"No local tools registered for MCP {mcp_id}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_executors.py tests/test_api_agents.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/services/mcp_tool_registry.py app/services/agent_factory.py app/services/mcp_executor.py
git commit -m "refactor: consolidate triple MCP tool mapping into single registry"
```

---

### Task 21: Add Missing Database Indexes (Performance)

**Files:**
- Create: `migrations/versions/012_add_performance_indexes.py`

- [ ] **Step 1: Write migration with all missing indexes**

```python
"""add performance indexes

Revision ID: 012
Revises: 011_add_foreign_keys
"""
from alembic import op

revision = "012_add_performance_indexes"
down_revision = "011_add_foreign_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Subagent invocations
    op.create_index("ix_subagent_inv_agent_id", "subagent_invocations", ["agent_id"])
    op.create_index("ix_subagent_inv_status", "subagent_invocations", ["status"])

    # MCP invocations
    op.create_index("ix_mcp_inv_mcp_id", "mcp_invocations", ["mcp_id"])
    op.create_index("ix_mcp_inv_status", "mcp_invocations", ["status"])

    # Cases and requests
    op.create_index("ix_cases_tenant_id", "cases", ["tenant_id"])
    op.create_index("ix_requests_tenant_id", "requests", ["tenant_id"])

    # Approval requests
    op.create_index("ix_approval_requests_case_id", "approval_requests", ["case_id"])

    # Composite indexes for common query patterns
    op.create_index("ix_run_nodes_run_status", "run_nodes", ["run_id", "status"])
    op.create_index("ix_audit_events_run_type", "audit_events", ["run_id", "event_type"])
    op.create_index("ix_agent_test_runs_agent_created",
                    "agent_test_runs", ["agent_id", "created_at"])
    op.create_index("ix_test_runs_scenario_status",
                    "test_runs", ["scenario_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_test_runs_scenario_status")
    op.drop_index("ix_agent_test_runs_agent_created")
    op.drop_index("ix_audit_events_run_type")
    op.drop_index("ix_run_nodes_run_status")
    op.drop_index("ix_approval_requests_case_id")
    op.drop_index("ix_requests_tenant_id")
    op.drop_index("ix_cases_tenant_id")
    op.drop_index("ix_mcp_inv_status")
    op.drop_index("ix_mcp_inv_mcp_id")
    op.drop_index("ix_subagent_inv_status")
    op.drop_index("ix_subagent_inv_agent_id")
```

- [ ] **Step 2: Apply migration**

```bash
alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add migrations/versions/012_add_performance_indexes.py
git commit -m "perf: add missing database indexes for common query patterns"
```

---

### Task 22: Use StatCard Component Everywhere (F29)

**Files:**
- Modify: `frontend/src/app/agents/page.tsx` (remove inline StatCard)
- Modify: `frontend/src/app/mcps/page.tsx` (remove inline StatCard)
- Modify: `frontend/src/app/mcps/[id]/toolkit/page.tsx` (remove inline StatCard)

- [ ] **Step 1: Replace inline StatCard definitions with the shared component**

In each of the 3 files, remove the local `function StatCard(...)` definition and import instead:

```typescript
import { StatCard } from "@/components/ui/stat-card";
```

Adjust props if the shared component has a different interface. If needed, update the shared component to support all use cases.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/agents/page.tsx frontend/src/app/mcps/page.tsx frontend/src/app/mcps/\\[id\\]/toolkit/page.tsx
git commit -m "refactor(F29): use shared StatCard component instead of inline definitions"
```

---

## Phase 2 -- Industrialization (Findings F05, F11, F13, F28, F30, F31)

---

### Task 23: Add Test Lab Config Validation (F11)

**Files:**
- Create: `app/schemas/test_lab_config.py`
- Modify: `app/api/routes/test_lab.py` (validate config before persisting)

- [ ] **Step 1: Create config validation schema**

Create `app/schemas/test_lab_config.py`:

```python
"""Validation schema for Test Lab configuration."""
from pydantic import BaseModel, Field
from typing import Optional


class TestLabConfig(BaseModel):
    default_agent_id: Optional[str] = None
    default_timeout_seconds: int = Field(default=120, ge=10, le=600)
    default_max_iterations: int = Field(default=5, ge=1, le=20)
    default_model_provider: str = Field(default="ollama", pattern="^(ollama|openai)$")
    default_model_name: str = Field(default="mistral")
    scoring_pass_threshold: int = Field(default=80, ge=0, le=100)
    scoring_warning_threshold: int = Field(default=50, ge=0, le=100)
```

- [ ] **Step 2: Use it in the update_config route**

In `app/api/routes/test_lab.py`, in `update_config`:

```python
from app.schemas.test_lab_config import TestLabConfig

@router.put("/config")
async def update_config(body: TestLabConfig, db: AsyncSession = Depends(get_db)):
    # body is already validated by Pydantic
    config_dict = body.model_dump(exclude_unset=True)
    # ... persist to DB ...
```

- [ ] **Step 3: Commit**

```bash
git add app/schemas/test_lab_config.py app/api/routes/test_lab.py
git commit -m "fix(F11): validate test lab config with Pydantic schema before persisting"
```

---

### Task 24: Add LLM Output Validation (F13)

**Files:**
- Create: `app/services/llm_output_validator.py`
- Modify: `app/services/agent_test_service.py` (validate output post-LLM)
- Modify: `app/services/subagent_executor.py` (validate output post-LLM)

- [ ] **Step 1: Create output validator**

Create `app/services/llm_output_validator.py`:

```python
"""Post-LLM output validation -- checks forbidden effects and output structure."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ValidationResult:
    def __init__(self, valid: bool, violations: list[str] = None):
        self.valid = valid
        self.violations = violations or []


def validate_forbidden_effects(
    output: str,
    forbidden_effects: list[str],
) -> ValidationResult:
    """Check if the LLM output contains forbidden effects.

    This is a deterministic post-LLM guardrail.
    """
    violations = []

    effect_patterns = {
        "publish": ["published", "i have published", "sent to production", "deployed"],
        "approve": ["i approve", "approved the", "giving approval"],
        "external_act": ["sent email", "posted to", "called external api"],
        "final_decision": ["final decision is", "i have decided"],
    }

    output_lower = output.lower()
    for effect in forbidden_effects:
        patterns = effect_patterns.get(effect, [])
        for pattern in patterns:
            if pattern in output_lower:
                violations.append(
                    f"Forbidden effect '{effect}' detected: output contains '{pattern}'"
                )

    return ValidationResult(valid=len(violations) == 0, violations=violations)


def validate_output_structure(
    output: str,
    expected_format: Optional[str] = None,
) -> ValidationResult:
    """Basic structural validation of LLM output."""
    violations = []

    if not output or not output.strip():
        violations.append("Output is empty")

    if len(output.strip()) < 10:
        violations.append("Output is suspiciously short (< 10 chars)")

    return ValidationResult(valid=len(violations) == 0, violations=violations)
```

- [ ] **Step 2: Integrate into agent_test_service**

In `app/services/agent_test_service.py`, after the LLM call returns `raw_output`, add:

```python
from app.services.llm_output_validator import validate_forbidden_effects, validate_output_structure

# After getting raw_output from the agent:
forbidden = agent.forbidden_effects or []
fx_check = validate_forbidden_effects(raw_output, forbidden)
struct_check = validate_output_structure(raw_output)

if not fx_check.valid:
    result["forbidden_effect_violations"] = fx_check.violations
    result["verdict"] = "fail"

if not struct_check.valid:
    result["structure_violations"] = struct_check.violations
```

- [ ] **Step 3: Commit**

```bash
git add app/services/llm_output_validator.py app/services/agent_test_service.py
git commit -m "feat(F13): add deterministic post-LLM output validation for forbidden effects"
```

---

### Task 25: Configure Structlog (F31)

**Files:**
- Create: `app/core/logging.py`
- Modify: `app/main.py` (call configure on startup)

- [ ] **Step 1: Create logging configuration**

Create `app/core/logging.py`:

```python
"""Structured logging configuration using structlog."""
import logging
import structlog
from app.core.config import get_settings


def configure_logging():
    settings = get_settings()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
```

- [ ] **Step 2: Call configure in app startup**

In `app/main.py`, in the lifespan function, at the start:

```python
from app.core.logging import configure_logging

@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_logging()
    # ... rest of startup ...
```

- [ ] **Step 3: Commit**

```bash
git add app/core/logging.py app/main.py
git commit -m "feat(F31): configure structlog for structured JSON logging"
```

---

### Task 26: Add Global Exception Handler (Backend quality)

**Files:**
- Create: `app/core/exceptions.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create exception hierarchy**

Create `app/core/exceptions.py`:

```python
"""Custom exception hierarchy for Orkestra."""


class OrkestraError(Exception):
    """Base exception for all Orkestra errors."""
    pass


class NotFoundError(OrkestraError):
    """Resource not found."""
    pass


class ValidationError(OrkestraError):
    """Input validation failed."""
    pass


class StateViolationError(OrkestraError):
    """Invalid state transition attempted."""
    pass


class AuthorizationError(OrkestraError):
    """Insufficient permissions."""
    pass
```

- [ ] **Step 2: Add global exception handlers in main.py**

In `app/main.py`:

```python
from fastapi.responses import JSONResponse
from app.core.exceptions import NotFoundError, ValidationError, StateViolationError

@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(ValidationError)
async def validation_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})

@app.exception_handler(StateViolationError)
async def state_violation_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(Exception)
async def generic_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

- [ ] **Step 3: Commit**

```bash
git add app/core/exceptions.py app/main.py
git commit -m "feat: add custom exception hierarchy and global exception handlers"
```

---

### Task 27: Add Redis Cache for Obot Catalog (Performance)

**Files:**
- Modify: `app/services/obot_catalog_service.py`

- [ ] **Step 1: Add Redis caching to catalog fetch**

In `app/services/obot_catalog_service.py`, add caching around `fetch_obot_servers()`:

```python
import json
import redis.asyncio as aioredis
from app.core.config import get_settings

CACHE_TTL = 300  # 5 minutes

async def _get_redis():
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL)


async def fetch_obot_servers(force_refresh: bool = False) -> list[dict]:
    """Fetch Obot servers with Redis caching."""
    r = await _get_redis()
    cache_key = "orkestra:obot_catalog"

    if not force_refresh:
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)

    # ... existing fetch logic ...
    servers = await _fetch_from_obot_api()

    # Cache the result
    await r.setex(cache_key, CACHE_TTL, json.dumps(servers, default=str))
    await r.aclose()

    return servers
```

- [ ] **Step 2: Invalidate cache on sync/import**

In the `sync_catalog()` and `import_catalog()` functions, add `force_refresh=True`.

- [ ] **Step 3: Commit**

```bash
git add app/services/obot_catalog_service.py
git commit -m "perf(F25): add Redis cache for Obot catalog with 5min TTL"
```

---

### Task 28: Add Correlation ID Middleware (Observability)

**Files:**
- Create: `app/core/correlation.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create correlation ID middleware**

Create `app/core/correlation.py`:

```python
"""Correlation ID middleware for request tracing."""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
```

- [ ] **Step 2: Wire into app**

In `app/main.py`, add before other middleware:

```python
from app.core.correlation import CorrelationIdMiddleware
app.add_middleware(CorrelationIdMiddleware)
```

- [ ] **Step 3: Commit**

```bash
git add app/core/correlation.py app/main.py
git commit -m "feat: add correlation ID middleware for end-to-end request tracing"
```

---

### Task 29: Validate Test Lab Config Endpoint Security (F11)

**Files:**
- Modify: `app/api/routes/test_lab.py` (the `update_config` raw SQL)

- [ ] **Step 1: Replace raw SQL with proper ORM insert/update**

The current `update_config` uses `conn.execute(text("INSERT OR UPDATE..."))`. Replace with a proper pattern using the `test_lab_config` table as a key-value store with validated keys:

```python
ALLOWED_CONFIG_KEYS = {
    "default_agent_id", "default_timeout_seconds", "default_max_iterations",
    "default_model_provider", "default_model_name",
    "scoring_pass_threshold", "scoring_warning_threshold",
}

@router.put("/config")
async def update_config(body: TestLabConfig, db: AsyncSession = Depends(get_db)):
    config_dict = body.model_dump(exclude_unset=True)
    # Only persist known keys
    for key, value in config_dict.items():
        if key not in ALLOWED_CONFIG_KEYS:
            continue
        # upsert logic using SQLAlchemy, not raw SQL
        ...
```

- [ ] **Step 2: Commit**

```bash
git add app/api/routes/test_lab.py
git commit -m "fix(F11): replace raw SQL in test lab config with validated ORM operations"
```

---

### Task 30: Install React Query for Frontend Data Management

**Files:**
- Modify: `frontend/package.json` (add @tanstack/react-query)
- Create: `frontend/src/lib/query-provider.tsx`
- Modify: `frontend/src/app/layout.tsx` (wrap with QueryProvider)

- [ ] **Step 1: Install React Query**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npm install @tanstack/react-query
```

- [ ] **Step 2: Create QueryProvider wrapper**

Create `frontend/src/lib/query-provider.tsx`:

```typescript
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, ReactNode } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000, // 30 seconds
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

- [ ] **Step 3: Wrap layout with QueryProvider**

In `frontend/src/app/layout.tsx`, wrap the children:

```typescript
import { QueryProvider } from "@/lib/query-provider";

// In the layout component, wrap:
<QueryProvider>
  <AppShell>{children}</AppShell>
</QueryProvider>
```

- [ ] **Step 4: Convert one page as example (agents list)**

In `frontend/src/app/agents/page.tsx`, replace the `useState`/`useEffect` data fetching with:

```typescript
import { useQuery } from "@tanstack/react-query";
import { agentRegistryService } from "@/lib/agent-registry/service";

// Replace:
// const [agents, setAgents] = useState([]);
// useEffect(() => { fetch... }, []);

// With:
const { data: agents = [], isLoading, error } = useQuery({
  queryKey: ["agents", filters],
  queryFn: () => agentRegistryService.listAgents(filters),
});
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: install React Query and convert agents page to use it"
```

---

## Phase 3 -- Scale-Up

---

### Task 31: Add Rate Limiting

**Files:**
- Modify: `pyproject.toml` (add slowapi)
- Create: `app/core/rate_limit.py`
- Modify: `app/main.py`

- [ ] **Step 1: Install slowapi**

```bash
pip install slowapi
```

Add `"slowapi>=0.1.9"` to `pyproject.toml` dependencies.

- [ ] **Step 2: Create rate limiter**

Create `app/core/rate_limit.py`:

```python
"""Rate limiting configuration."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
```

- [ ] **Step 3: Wire into app**

In `app/main.py`:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 4: Add specific limits on sensitive endpoints**

In `app/api/routes/settings.py`:

```python
from app.core.rate_limit import limiter

@router.put("/secrets/{secret_id}")
@limiter.limit("10/minute")
async def upsert_secret(request: Request, ...):
    ...
```

- [ ] **Step 5: Commit**

```bash
git add app/core/rate_limit.py app/main.py app/api/routes/settings.py pyproject.toml
git commit -m "feat: add rate limiting with slowapi"
```

---

### Task 32: Add MCP Runtime Enforcement (deterministic allowlist)

**Files:**
- Modify: `app/services/agent_factory.py` (filter toolkit to allowed MCPs only)

- [ ] **Step 1: Enforce allowlist in create_agentscope_agent**

In `app/services/agent_factory.py`, in `create_agentscope_agent()`, when building the toolkit, only register tools from MCPs that are in `agent_def.allowed_mcps`:

```python
# Before registering tools in the Toolkit:
allowed = set(agent_def.allowed_mcps or [])

for mcp_id, tools in resolved_tools.items():
    if allowed and mcp_id not in allowed:
        logger.warning(f"Skipping MCP {mcp_id}: not in agent's allowed_mcps")
        continue
    for tool in tools:
        toolkit.register(tool)
```

This ensures the LLM physically cannot call unauthorized tools, regardless of what the prompt says.

- [ ] **Step 2: Commit**

```bash
git add app/services/agent_factory.py
git commit -m "feat: enforce MCP allowlist deterministically in agent toolkit, not just in prompt"
```

---

### Task 33: Move Text Search to Database (Performance)

**Files:**
- Modify: `app/services/agent_registry_service.py` (list_agents filter)

- [ ] **Step 1: Replace in-memory text search with SQL ILIKE**

In `agent_registry_service.py`, in `list_agents`, move the `q` text filter to the SQL query:

```python
if q:
    pattern = f"%{q}%"
    stmt = stmt.where(
        or_(
            AgentDefinition.id.ilike(pattern),
            AgentDefinition.name.ilike(pattern),
            AgentDefinition.purpose.ilike(pattern),
            AgentDefinition.description.ilike(pattern),
        )
    )
```

Remove the Python-side `_matches_text` filtering.

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_api_agents.py tests/test_api_agent_registry_product.py -v
```

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_registry_service.py
git commit -m "perf: move agent text search from Python to SQL ILIKE"
```

---

### Task 34: Add MCP Definition History Table

**Files:**
- Create: `migrations/versions/013_mcp_definition_history.py`
- Create: `app/models/mcp_history.py`
- Modify: `app/services/mcp_registry_service.py` (snapshot before update)

- [ ] **Step 1: Create model**

Create `app/models/mcp_history.py`:

```python
"""History tracking for MCP definitions."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class MCPDefinitionHistory(Base):
    __tablename__ = "mcp_definition_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mcp_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("mcp_definitions.id", ondelete="CASCADE"), index=True
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(20))
    replaced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Write migration**

Create `migrations/versions/013_mcp_definition_history.py` with the table creation.

- [ ] **Step 3: Add snapshot logic to mcp_registry_service update function**

Same pattern as agent/family/skill: snapshot current state before applying update.

- [ ] **Step 4: Commit**

```bash
git add app/models/mcp_history.py migrations/versions/013_mcp_definition_history.py app/services/mcp_registry_service.py
git commit -m "feat: add MCP definition history table for audit trail"
```

---

### Task 35: Add Accessibility Basics (F30)

**Files:**
- Modify: `frontend/src/components/agents/agent-form.tsx` (add label associations)
- Modify: `frontend/src/components/agents/family-form-modal.tsx` (add aria attributes)
- Modify: `frontend/src/components/agents/skill-form-modal.tsx` (add aria attributes)
- Modify: `frontend/src/components/agents/generate-agent-modal.tsx` (add focus trap)
- Modify: `frontend/src/components/ui/status-badge.tsx` (add aria-label)

- [ ] **Step 1: Add htmlFor on agent form labels**

In `agent-form.tsx`, replace `<p className="data-label">Name</p>` with:

```tsx
<label htmlFor="agent-name" className="data-label">Name</label>
<input id="agent-name" ... />
```

Apply to all form fields.

- [ ] **Step 2: Add aria attributes to modals**

In each modal component, add to the overlay div:

```tsx
<div role="dialog" aria-modal="true" aria-labelledby="modal-title" className="fixed inset-0 z-50...">
  <h2 id="modal-title">...</h2>
```

- [ ] **Step 3: Add aria-label to StatusBadge**

In `status-badge.tsx`:

```tsx
<span className={...} role="status" aria-label={`Status: ${status}`}>
  {status}
</span>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/
git commit -m "a11y(F30): add label associations, ARIA attributes, and status roles"
```

---

### Task 36: Remove Docker Socket Mount from Obot (F12)

**Files:**
- Modify: `docker-compose.yml:62`

- [ ] **Step 1: Remove the docker socket mount**

In `docker-compose.yml`, in the `obot` service, remove:

```yaml
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

If Obot absolutely requires Docker access, isolate it with a Docker-in-Docker sidecar or a rootless Docker proxy.

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "fix(F12): remove Docker socket mount from Obot service"
```

---

### Task 37: Rename generate-draft to be Honest (F28)

**Files:**
- Modify: `app/api/routes/agents.py` (rename endpoint)
- Modify: `app/services/agent_generation_service.py` (rename function)
- Modify: `frontend/src/components/agents/generate-agent-modal.tsx` (update label)

- [ ] **Step 1: Rename backend endpoint and service**

In `app/api/routes/agents.py`, rename `/generate-draft` to `/generate-draft-template`:

```python
@router.post("/generate-draft-template")
async def generate_agent_draft_template(...):
```

In `agent_generation_service.py`, rename `generate_agent_draft` to `generate_agent_template` and change `source` from `"mock_llm"` to `"heuristic_template"`.

- [ ] **Step 2: Update frontend**

In `generate-agent-modal.tsx`, update the fetch URL and change the UI copy from "AI-Powered Generation" to "Template-Based Draft" or similar.

- [ ] **Step 3: Commit**

```bash
git add app/api/routes/agents.py app/services/agent_generation_service.py frontend/src/components/agents/generate-agent-modal.tsx
git commit -m "fix(F28): rename generate-draft to template-based draft, remove misleading AI label"
```

---

## Summary of All Tasks by Phase

| Phase | Tasks | Findings Addressed |
|-------|-------|--------------------|
| **Phase 0** -- Critical Fixes | Tasks 1-8 | F01, F02, F03, F04, F06, F07, F08, F18, F19 |
| **Phase 1** -- Architecture Stabilization | Tasks 9-22 | F05 (partial), F09, F10, F14, F15, F16, F17, F20, F21, F22, F23, F24, F26, F27, F29 |
| **Phase 2** -- Industrialization | Tasks 23-30 | F05 (partial), F11, F13, F25, F28, F30, F31 |
| **Phase 3** -- Scale-Up | Tasks 31-37 | F12, F28, F30, rate limiting, MCP enforcement, text search, MCP history |

---

## Execution Dependencies

```
Phase 0 (Tasks 1-8) -- no dependencies, can run in parallel
  |
  v
Phase 1 (Tasks 9-22)
  Task 11 depends on Task 1 (FK migration needs test lab tables)
  Task 12 depends on nothing
  Tasks 9-10, 13-22 are independent
  |
  v
Phase 2 (Tasks 23-30)
  Task 23 depends on nothing
  Task 25 depends on nothing
  Task 27 depends on nothing
  Task 30 depends on Task 18 (unified API client)
  |
  v
Phase 3 (Tasks 31-37)
  Task 31 depends on Task 2 (auth middleware exists)
  Task 32 depends on Task 20 (unified MCP registry)
  Tasks 33-37 are independent
```
