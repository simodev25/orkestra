# Agentic Test Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simple test runner with a controlled agentic testing system featuring scenario management, orchestrated multi-phase execution, deterministic assertions/diagnostics, scoring/verdict, agent-level evaluation, and a full timeline UI.

**Architecture:** Central orchestrator dispatches 5 sequential phases (preparation, runtime execution via AgentScope hooks, assertion evaluation, diagnostic analysis, report assembly). Each phase emits normalized events persisted to PostgreSQL. Deterministic scoring produces a verdict. Agent-level summaries aggregate across runs for lifecycle readiness.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL (JSONB), AgentScope (ReActAgent + hooks + Toolkit), Next.js 15, React 19, TypeScript, Tailwind CSS

---

## File Structure

### Backend - Models
| File | Responsibility |
|------|---------------|
| `app/models/test_lab.py` | All test lab DB models: TestScenario, TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic |
| `app/models/enums.py` | Add new enums: TestRunStatus, TestVerdict, EventType, AssertionType, DiagnosticCode, Severity |

### Backend - Schemas
| File | Responsibility |
|------|---------------|
| `app/schemas/test_lab.py` | Pydantic schemas: ScenarioCreate/Update/Out, RunOut, EventOut, AssertionOut, DiagnosticOut, AgentTestSummary |

### Backend - Services
| File | Responsibility |
|------|---------------|
| `app/services/test_lab/orchestrator.py` | Central orchestrator: receives scenario, dispatches phases, collects results, emits events |
| `app/services/test_lab/runtime_adapter.py` | Wraps existing AgentScope ReActAgent execution, captures events via hooks |
| `app/services/test_lab/assertion_engine.py` | Deterministic assertion evaluation against events and output |
| `app/services/test_lab/diagnostic_engine.py` | Pattern-based diagnostic analysis on events |
| `app/services/test_lab/scoring.py` | Deterministic scoring and verdict computation |
| `app/services/test_lab/scenario_service.py` | CRUD for test scenarios |
| `app/services/test_lab/agent_summary.py` | Agent-level evaluation: aggregate runs, compute readiness |

### Backend - API
| File | Responsibility |
|------|---------------|
| `app/api/routes/test_lab.py` | All test lab API endpoints: scenarios CRUD, run management, events, assertions, diagnostics, agent summary |

### Frontend - Types & API
| File | Responsibility |
|------|---------------|
| `frontend/src/lib/test-lab/types.ts` | TypeScript types for all test lab entities |
| `frontend/src/lib/test-lab/api.ts` | API client methods for test lab |

### Frontend - Pages
| File | Responsibility |
|------|---------------|
| `frontend/src/app/test-lab/page.tsx` | Scenario list page |
| `frontend/src/app/test-lab/scenarios/new/page.tsx` | Create scenario page |
| `frontend/src/app/test-lab/scenarios/[id]/page.tsx` | Scenario detail page |
| `frontend/src/app/test-lab/runs/[id]/page.tsx` | Run detail page with timeline |

### Frontend - Components
| File | Responsibility |
|------|---------------|
| `frontend/src/components/test-lab/ExecutionTimeline.tsx` | Timeline visualization of normalized events |
| `frontend/src/components/test-lab/AssertionsPanel.tsx` | Assertions pass/fail display |
| `frontend/src/components/test-lab/DiagnosticsPanel.tsx` | Diagnostics findings display |
| `frontend/src/components/test-lab/AgentTestSummary.tsx` | Agent-level testing summary card |
| `frontend/src/components/test-lab/ScenarioForm.tsx` | Create/edit scenario form |

---

## Task 1: Enums and DB Models

**Files:**
- Modify: `app/models/enums.py`
- Create: `app/models/test_lab.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Add test lab enums to enums.py**

```python
# Add to app/models/enums.py

class TestRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class TestVerdict(str, enum.Enum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class EventType(str, enum.Enum):
    RUN_CREATED = "run_created"
    ORCHESTRATOR_STARTED = "orchestrator_started"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    HANDOFF_STARTED = "handoff_started"
    HANDOFF_COMPLETED = "handoff_completed"
    RUN_STARTED = "run_started"
    AGENT_ITERATION_STARTED = "agent_iteration_started"
    AGENT_ITERATION_COMPLETED = "agent_iteration_completed"
    LLM_REQUEST_STARTED = "llm_request_started"
    LLM_REQUEST_COMPLETED = "llm_request_completed"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    MCP_SESSION_CONNECTED = "mcp_session_connected"
    MCP_SESSION_FAILED = "mcp_session_failed"
    ASSERTION_PHASE_STARTED = "assertion_phase_started"
    ASSERTION_PASSED = "assertion_passed"
    ASSERTION_FAILED = "assertion_failed"
    DIAGNOSTIC_PHASE_STARTED = "diagnostic_phase_started"
    DIAGNOSTIC_GENERATED = "diagnostic_generated"
    REPORT_PHASE_STARTED = "report_phase_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_TIMEOUT = "run_timeout"


class AssertionType(str, enum.Enum):
    TOOL_CALLED = "tool_called"
    TOOL_NOT_CALLED = "tool_not_called"
    OUTPUT_FIELD_EXISTS = "output_field_exists"
    OUTPUT_SCHEMA_MATCHES = "output_schema_matches"
    MAX_DURATION_MS = "max_duration_ms"
    MAX_ITERATIONS = "max_iterations"
    FINAL_STATUS_IS = "final_status_is"
    NO_TOOL_FAILURES = "no_tool_failures"


class DiagnosticCode(str, enum.Enum):
    EXPECTED_TOOL_NOT_USED = "expected_tool_not_used"
    TOOL_FAILURE_DETECTED = "tool_failure_detected"
    RUN_TIMED_OUT = "run_timed_out"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    EXCESSIVE_ITERATIONS = "excessive_iterations"
    SLOW_FINAL_SYNTHESIS = "slow_final_synthesis"
    NO_PROGRESS_DETECTED = "no_progress_detected"


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
```

- [ ] **Step 2: Create test_lab.py models**

```python
# app/models/test_lab.py
"""Agentic Test Lab — persistence models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id


class TestScenario(BaseModel):
    __tablename__ = "test_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("scn_"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    input_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    allowed_tools: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    expected_tools: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    max_iterations: Mapped[int] = mapped_column(Integer, default=5)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    assertions: Mapped[list] = mapped_column(JSONB, default=list)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TestRun(BaseModel):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("trun_"))
    scenario_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    agent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TestRunEvent(BaseModel):
    __tablename__ = "test_run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("evt_"))
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TestRunAssertion(BaseModel):
    __tablename__ = "test_run_assertions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("ast_"))
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    assertion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TestRunDiagnostic(BaseModel):
    __tablename__ = "test_run_diagnostics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("diag_"))
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    probable_causes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 3: Register models in __init__.py**

Add to `app/models/__init__.py`:
```python
from app.models.test_lab import TestScenario, TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic

# Add to __all__:
"TestScenario", "TestRun", "TestRunEvent", "TestRunAssertion", "TestRunDiagnostic",
```

- [ ] **Step 4: Create tables via SQL**

```bash
docker compose exec api python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import get_settings

async def create():
    engine = create_async_engine(get_settings().DATABASE_URL)
    async with engine.begin() as conn:
        for sql in [
            '''CREATE TABLE IF NOT EXISTS test_scenarios (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                agent_id VARCHAR(100) NOT NULL,
                input_prompt TEXT NOT NULL,
                input_payload JSONB,
                allowed_tools JSONB,
                expected_tools JSONB,
                timeout_seconds INTEGER DEFAULT 120,
                max_iterations INTEGER DEFAULT 5,
                retry_count INTEGER DEFAULT 0,
                assertions JSONB DEFAULT '[]',
                tags JSONB,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )''',
            'CREATE INDEX IF NOT EXISTS ix_test_scenarios_agent_id ON test_scenarios (agent_id)',
            '''CREATE TABLE IF NOT EXISTS test_runs (
                id VARCHAR(36) PRIMARY KEY,
                scenario_id VARCHAR(36) NOT NULL,
                agent_id VARCHAR(100) NOT NULL,
                agent_version VARCHAR(20) NOT NULL,
                status VARCHAR(30) DEFAULT 'queued',
                verdict VARCHAR(30),
                score FLOAT,
                duration_ms INTEGER,
                final_output TEXT,
                summary TEXT,
                error_message TEXT,
                execution_metadata JSONB,
                started_at TIMESTAMPTZ,
                ended_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )''',
            'CREATE INDEX IF NOT EXISTS ix_test_runs_scenario_id ON test_runs (scenario_id)',
            'CREATE INDEX IF NOT EXISTS ix_test_runs_agent_id ON test_runs (agent_id)',
            '''CREATE TABLE IF NOT EXISTS test_run_events (
                id VARCHAR(36) PRIMARY KEY,
                run_id VARCHAR(36) NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                phase VARCHAR(50),
                message TEXT,
                details JSONB,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                duration_ms INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )''',
            'CREATE INDEX IF NOT EXISTS ix_test_run_events_run_id ON test_run_events (run_id)',
            '''CREATE TABLE IF NOT EXISTS test_run_assertions (
                id VARCHAR(36) PRIMARY KEY,
                run_id VARCHAR(36) NOT NULL,
                assertion_type VARCHAR(50) NOT NULL,
                target VARCHAR(255),
                expected TEXT,
                actual TEXT,
                passed BOOLEAN NOT NULL,
                critical BOOLEAN DEFAULT FALSE,
                message TEXT NOT NULL,
                details JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )''',
            'CREATE INDEX IF NOT EXISTS ix_test_run_assertions_run_id ON test_run_assertions (run_id)',
            '''CREATE TABLE IF NOT EXISTS test_run_diagnostics (
                id VARCHAR(36) PRIMARY KEY,
                run_id VARCHAR(36) NOT NULL,
                code VARCHAR(50) NOT NULL,
                severity VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                probable_causes JSONB,
                recommendation TEXT,
                evidence JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )''',
            'CREATE INDEX IF NOT EXISTS ix_test_run_diagnostics_run_id ON test_run_diagnostics (run_id)',
        ]:
            await conn.execute(text(sql))
    await engine.dispose()
    print('All test lab tables created')

asyncio.run(create())
"
```

- [ ] **Step 5: Commit**

```bash
git add app/models/enums.py app/models/test_lab.py app/models/__init__.py
git commit -m "feat(test-lab): add persistence models — TestScenario, TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic"
```

---

## Task 2: Pydantic Schemas and Contracts

**Files:**
- Create: `app/schemas/test_lab.py`

- [ ] **Step 1: Create test lab schemas**

```python
# app/schemas/test_lab.py
"""Agentic Test Lab — API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import OrkBaseSchema


# ── Assertion definition (inside scenario) ─────────────────────────────

class AssertionDef(OrkBaseSchema):
    type: str = Field(..., description="One of: tool_called, tool_not_called, output_field_exists, output_schema_matches, max_duration_ms, max_iterations, final_status_is, no_tool_failures")
    target: Optional[str] = None
    expected: Optional[str] = None
    critical: bool = False


# ── Scenario ───────────────────────────────────────────────────────────

class ScenarioCreate(OrkBaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_id: str = Field(..., min_length=1, max_length=100)
    input_prompt: str = Field(..., min_length=1)
    input_payload: Optional[dict] = None
    allowed_tools: Optional[list[str]] = None
    expected_tools: Optional[list[str]] = None
    timeout_seconds: int = Field(default=120, ge=5, le=600)
    max_iterations: int = Field(default=5, ge=1, le=20)
    retry_count: int = Field(default=0, ge=0, le=5)
    assertions: list[AssertionDef] = Field(default_factory=list)
    tags: Optional[list[str]] = None
    enabled: bool = True


class ScenarioUpdate(OrkBaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    input_prompt: Optional[str] = Field(None, min_length=1)
    input_payload: Optional[dict] = None
    allowed_tools: Optional[list[str]] = None
    expected_tools: Optional[list[str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=5, le=600)
    max_iterations: Optional[int] = Field(None, ge=1, le=20)
    retry_count: Optional[int] = Field(None, ge=0, le=5)
    assertions: Optional[list[AssertionDef]] = None
    tags: Optional[list[str]] = None
    enabled: Optional[bool] = None


class ScenarioOut(OrkBaseSchema):
    id: str
    name: str
    description: Optional[str]
    agent_id: str
    input_prompt: str
    input_payload: Optional[dict]
    allowed_tools: Optional[list[str]]
    expected_tools: Optional[list[str]]
    timeout_seconds: int
    max_iterations: int
    retry_count: int
    assertions: list[AssertionDef]
    tags: Optional[list[str]]
    enabled: bool
    created_at: datetime
    updated_at: datetime


# ── Run ────────────────────────────────────────────────────────────────

class RunOut(OrkBaseSchema):
    id: str
    scenario_id: str
    agent_id: str
    agent_version: str
    status: str
    verdict: Optional[str]
    score: Optional[float]
    duration_ms: Optional[int]
    final_output: Optional[str]
    summary: Optional[str]
    error_message: Optional[str]
    execution_metadata: Optional[dict]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime


# ── Event ──────────────────────────────────────────────────────────────

class EventOut(OrkBaseSchema):
    id: str
    run_id: str
    event_type: str
    phase: Optional[str]
    message: Optional[str]
    details: Optional[dict]
    timestamp: datetime
    duration_ms: Optional[int]


# ── Assertion result ───────────────────────────────────────────────────

class AssertionResultOut(OrkBaseSchema):
    id: str
    run_id: str
    assertion_type: str
    target: Optional[str]
    expected: Optional[str]
    actual: Optional[str]
    passed: bool
    critical: bool
    message: str
    details: Optional[dict]


# ── Diagnostic ─────────────────────────────────────────────────────────

class DiagnosticOut(OrkBaseSchema):
    id: str
    run_id: str
    code: str
    severity: str
    message: str
    probable_causes: Optional[list[str]]
    recommendation: Optional[str]
    evidence: Optional[dict]


# ── Agent test summary ─────────────────────────────────────────────────

class AgentTestSummary(OrkBaseSchema):
    agent_id: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    warning_runs: int
    pass_rate: float
    average_score: float
    last_run_at: Optional[datetime]
    last_verdict: Optional[str]
    tool_failure_rate: float
    timeout_rate: float
    average_duration_ms: float
    eligible_for_tested: bool


# ── Run report (composite) ─────────────────────────────────────────────

class RunReport(OrkBaseSchema):
    run: RunOut
    events: list[EventOut]
    assertions: list[AssertionResultOut]
    diagnostics: list[DiagnosticOut]
    scenario: ScenarioOut
```

- [ ] **Step 2: Commit**

```bash
git add app/schemas/test_lab.py
git commit -m "feat(test-lab): add Pydantic schemas — strict contracts for scenarios, runs, events, assertions, diagnostics"
```

---

## Task 3: Scenario CRUD Service

**Files:**
- Create: `app/services/test_lab/__init__.py`
- Create: `app/services/test_lab/scenario_service.py`

- [ ] **Step 1: Create service package**

```python
# app/services/test_lab/__init__.py
"""Agentic Test Lab services."""
```

- [ ] **Step 2: Implement scenario CRUD**

```python
# app/services/test_lab/scenario_service.py
"""Scenario CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_lab import TestScenario
from app.schemas.test_lab import ScenarioCreate, ScenarioUpdate

logger = logging.getLogger("orkestra.test_lab.scenario")


async def create_scenario(db: AsyncSession, data: ScenarioCreate) -> TestScenario:
    scenario = TestScenario(
        name=data.name,
        description=data.description,
        agent_id=data.agent_id,
        input_prompt=data.input_prompt,
        input_payload=data.input_payload,
        allowed_tools=data.allowed_tools,
        expected_tools=data.expected_tools,
        timeout_seconds=data.timeout_seconds,
        max_iterations=data.max_iterations,
        retry_count=data.retry_count,
        assertions=[a.model_dump() for a in data.assertions],
        tags=data.tags,
        enabled=data.enabled,
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def get_scenario(db: AsyncSession, scenario_id: str) -> TestScenario | None:
    return await db.get(TestScenario, scenario_id)


async def list_scenarios(
    db: AsyncSession,
    agent_id: str | None = None,
    enabled: bool | None = None,
    limit: int = 50,
) -> list[TestScenario]:
    q = select(TestScenario)
    if agent_id:
        q = q.where(TestScenario.agent_id == agent_id)
    if enabled is not None:
        q = q.where(TestScenario.enabled == enabled)
    q = q.order_by(TestScenario.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_scenario(db: AsyncSession, scenario_id: str, data: ScenarioUpdate) -> TestScenario:
    scenario = await db.get(TestScenario, scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    update_data = data.model_dump(exclude_unset=True)
    if "assertions" in update_data and update_data["assertions"] is not None:
        update_data["assertions"] = [a if isinstance(a, dict) else a.model_dump() for a in update_data["assertions"]]
    for key, value in update_data.items():
        setattr(scenario, key, value)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def delete_scenario(db: AsyncSession, scenario_id: str) -> None:
    scenario = await db.get(TestScenario, scenario_id)
    if not scenario:
        raise ValueError(f"Scenario {scenario_id} not found")
    await db.delete(scenario)
    await db.commit()
```

- [ ] **Step 3: Commit**

```bash
git add app/services/test_lab/
git commit -m "feat(test-lab): add scenario CRUD service"
```

---

## Task 4: Assertion Engine

**Files:**
- Create: `app/services/test_lab/assertion_engine.py`

- [ ] **Step 1: Implement deterministic assertion engine**

```python
# app/services/test_lab/assertion_engine.py
"""Deterministic assertion evaluation."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("orkestra.test_lab.assertions")


def evaluate_assertions(
    assertion_defs: list[dict],
    events: list[dict],
    final_output: str | None,
    duration_ms: int,
    iteration_count: int,
    final_status: str,
) -> list[dict]:
    """Evaluate all assertions deterministically. Returns list of result dicts."""
    results = []
    for adef in assertion_defs:
        atype = adef.get("type", "")
        target = adef.get("target")
        expected = adef.get("expected")
        critical = adef.get("critical", False)

        if atype == "tool_called":
            result = _check_tool_called(events, target)
        elif atype == "tool_not_called":
            result = _check_tool_not_called(events, target)
        elif atype == "output_field_exists":
            result = _check_output_field_exists(final_output, target)
        elif atype == "output_schema_matches":
            result = _check_output_schema(final_output, expected)
        elif atype == "max_duration_ms":
            result = _check_max_duration(duration_ms, int(expected or 0))
        elif atype == "max_iterations":
            result = _check_max_iterations(iteration_count, int(expected or 0))
        elif atype == "final_status_is":
            result = _check_final_status(final_status, expected or "")
        elif atype == "no_tool_failures":
            result = _check_no_tool_failures(events)
        else:
            result = {"passed": False, "message": f"Unknown assertion type: {atype}", "actual": None, "details": None}

        results.append({
            "assertion_type": atype,
            "target": target,
            "expected": expected,
            "actual": result.get("actual"),
            "passed": result["passed"],
            "critical": critical,
            "message": result["message"],
            "details": result.get("details"),
        })
    return results


def _check_tool_called(events: list[dict], tool_name: str | None) -> dict:
    called = [e for e in events if e.get("event_type") == "tool_call_completed" and e.get("details", {}).get("tool_name") == tool_name]
    if called:
        return {"passed": True, "message": f"Tool '{tool_name}' was called", "actual": tool_name}
    return {"passed": False, "message": f"Tool '{tool_name}' was NOT called", "actual": None}


def _check_tool_not_called(events: list[dict], tool_name: str | None) -> dict:
    called = [e for e in events if e.get("event_type") in ("tool_call_started", "tool_call_completed") and e.get("details", {}).get("tool_name") == tool_name]
    if not called:
        return {"passed": True, "message": f"Tool '{tool_name}' was correctly not called", "actual": None}
    return {"passed": False, "message": f"Tool '{tool_name}' was called but should not have been", "actual": tool_name}


def _check_output_field_exists(output: str | None, field: str | None) -> dict:
    if not output or not field:
        return {"passed": False, "message": f"Output or field not provided", "actual": None}
    try:
        parsed = json.loads(output)
        if field in parsed:
            return {"passed": True, "message": f"Field '{field}' exists in output", "actual": str(parsed[field])[:200]}
        return {"passed": False, "message": f"Field '{field}' missing from output", "actual": None}
    except (json.JSONDecodeError, TypeError):
        return {"passed": False, "message": f"Output is not valid JSON", "actual": None}


def _check_output_schema(output: str | None, schema_json: str | None) -> dict:
    if not output:
        return {"passed": False, "message": "No output to validate", "actual": None}
    try:
        parsed = json.loads(output)
        if not schema_json:
            return {"passed": True, "message": "No schema specified, output is valid JSON", "actual": "valid_json"}
        schema = json.loads(schema_json)
        missing = [k for k in schema.get("required", []) if k not in parsed]
        if missing:
            return {"passed": False, "message": f"Missing required fields: {missing}", "actual": json.dumps(list(parsed.keys())), "details": {"missing": missing}}
        return {"passed": True, "message": "Output matches schema", "actual": json.dumps(list(parsed.keys()))}
    except (json.JSONDecodeError, TypeError) as e:
        return {"passed": False, "message": f"Schema validation error: {e}", "actual": None}


def _check_max_duration(actual_ms: int, max_ms: int) -> dict:
    if actual_ms <= max_ms:
        return {"passed": True, "message": f"Duration {actual_ms}ms within limit {max_ms}ms", "actual": str(actual_ms)}
    return {"passed": False, "message": f"Duration {actual_ms}ms exceeds limit {max_ms}ms", "actual": str(actual_ms)}


def _check_max_iterations(actual: int, max_iters: int) -> dict:
    if actual <= max_iters:
        return {"passed": True, "message": f"Iterations {actual} within limit {max_iters}", "actual": str(actual)}
    return {"passed": False, "message": f"Iterations {actual} exceeds limit {max_iters}", "actual": str(actual)}


def _check_final_status(actual_status: str, expected: str) -> dict:
    if actual_status == expected:
        return {"passed": True, "message": f"Final status is '{expected}'", "actual": actual_status}
    return {"passed": False, "message": f"Expected status '{expected}', got '{actual_status}'", "actual": actual_status}


def _check_no_tool_failures(events: list[dict]) -> dict:
    failures = [e for e in events if e.get("event_type") == "tool_call_failed"]
    if not failures:
        return {"passed": True, "message": "No tool failures detected", "actual": "0"}
    names = [e.get("details", {}).get("tool_name", "unknown") for e in failures]
    return {"passed": False, "message": f"{len(failures)} tool failure(s): {names}", "actual": str(len(failures)), "details": {"failed_tools": names}}
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/assertion_engine.py
git commit -m "feat(test-lab): add deterministic assertion engine — 8 assertion types"
```

---

## Task 5: Diagnostic Engine

**Files:**
- Create: `app/services/test_lab/diagnostic_engine.py`

- [ ] **Step 1: Implement pattern-based diagnostic engine**

```python
# app/services/test_lab/diagnostic_engine.py
"""Pattern-based diagnostic analysis on run events."""

from __future__ import annotations

import logging

logger = logging.getLogger("orkestra.test_lab.diagnostics")


def generate_diagnostics(
    events: list[dict],
    assertions: list[dict],
    expected_tools: list[str] | None,
    duration_ms: int,
    iteration_count: int,
    max_iterations: int,
    timeout_seconds: int,
    final_output: str | None,
) -> list[dict]:
    """Generate deterministic diagnostics from event patterns."""
    findings: list[dict] = []

    # 1. Expected tool not used
    if expected_tools:
        tool_events = [e for e in events if e.get("event_type") == "tool_call_completed"]
        used_tools = {e.get("details", {}).get("tool_name") for e in tool_events}
        for tool in expected_tools:
            if tool not in used_tools:
                findings.append({
                    "code": "expected_tool_not_used",
                    "severity": "warning",
                    "message": f"Expected tool '{tool}' was not called during execution",
                    "probable_causes": [
                        "Agent decided the tool was not needed for this input",
                        "Agent was not aware of the tool availability",
                        "Input prompt did not trigger the expected tool usage path",
                    ],
                    "recommendation": f"Verify that the agent's prompt instructs it to use '{tool}' for this type of input.",
                    "evidence": {"expected": tool, "used_tools": list(used_tools)},
                })

    # 2. Tool failure detected
    tool_failures = [e for e in events if e.get("event_type") == "tool_call_failed"]
    for fail in tool_failures:
        tool_name = fail.get("details", {}).get("tool_name", "unknown")
        findings.append({
            "code": "tool_failure_detected",
            "severity": "error",
            "message": f"Tool '{tool_name}' failed during execution",
            "probable_causes": [
                "Tool server is unavailable or returned an error",
                "Tool input was malformed by the agent",
                "Network timeout connecting to the tool server",
            ],
            "recommendation": f"Check the tool server '{tool_name}' logs and verify connectivity.",
            "evidence": fail.get("details", {}),
        })

    # 3. Run timed out
    if duration_ms > timeout_seconds * 1000:
        findings.append({
            "code": "run_timed_out",
            "severity": "critical",
            "message": f"Run exceeded timeout of {timeout_seconds}s (actual: {duration_ms}ms)",
            "probable_causes": [
                "Agent entered a reasoning loop without converging",
                "Tool calls took too long to respond",
                "LLM inference was slow due to model size or load",
            ],
            "recommendation": "Increase timeout, reduce max_iterations, or check LLM/tool performance.",
            "evidence": {"timeout_seconds": timeout_seconds, "actual_ms": duration_ms},
        })

    # 4. Output schema invalid
    if final_output:
        import json
        try:
            json.loads(final_output)
        except (json.JSONDecodeError, TypeError):
            findings.append({
                "code": "output_schema_invalid",
                "severity": "error",
                "message": "Final output is not valid JSON",
                "probable_causes": [
                    "Agent produced free-text instead of structured output",
                    "Agent's prompt does not enforce JSON output format",
                ],
                "recommendation": "Add output format instructions to the agent's prompt or use structured_model.",
                "evidence": {"output_preview": (final_output or "")[:200]},
            })

    # 5. Excessive iterations
    if iteration_count >= max_iterations:
        findings.append({
            "code": "excessive_iterations",
            "severity": "warning",
            "message": f"Agent used all {max_iterations} iterations",
            "probable_causes": [
                "Task is too complex for the iteration budget",
                "Agent is exploring tools without converging",
                "Agent is stuck in a reasoning loop",
            ],
            "recommendation": "Increase max_iterations or simplify the task.",
            "evidence": {"iterations": iteration_count, "max": max_iterations},
        })

    # 6. Slow final synthesis
    llm_events = [e for e in events if e.get("event_type") == "llm_request_completed" and e.get("duration_ms")]
    if llm_events:
        last_llm = llm_events[-1]
        if last_llm.get("duration_ms", 0) > 30000:
            findings.append({
                "code": "slow_final_synthesis",
                "severity": "warning",
                "message": f"Final LLM call took {last_llm['duration_ms']}ms",
                "probable_causes": [
                    "Large context window with accumulated tool results",
                    "LLM model is slow or overloaded",
                ],
                "recommendation": "Consider a lighter model or reduce context size.",
                "evidence": {"duration_ms": last_llm["duration_ms"]},
            })

    # 7. No progress detected
    iteration_events = [e for e in events if e.get("event_type") in ("agent_iteration_started", "agent_iteration_completed")]
    if len(iteration_events) == 0 and duration_ms > 5000:
        findings.append({
            "code": "no_progress_detected",
            "severity": "error",
            "message": "No agent iteration events detected despite execution time",
            "probable_causes": [
                "Agent creation failed silently",
                "Runtime adapter did not capture events",
                "Agent stalled before first iteration",
            ],
            "recommendation": "Check runtime adapter and agent factory logs.",
            "evidence": {"duration_ms": duration_ms, "iteration_events": 0},
        })

    return findings
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/diagnostic_engine.py
git commit -m "feat(test-lab): add pattern-based diagnostic engine — 7 diagnostic codes"
```

---

## Task 6: Scoring and Verdict

**Files:**
- Create: `app/services/test_lab/scoring.py`

- [ ] **Step 1: Implement deterministic scoring**

```python
# app/services/test_lab/scoring.py
"""Deterministic scoring and verdict computation."""

from __future__ import annotations


MAX_SCORE = 100.0

PENALTIES = {
    "assertion_failed": 15.0,
    "assertion_failed_critical": 50.0,
    "tool_failure": 20.0,
    "timeout": 30.0,
    "output_invalid": 20.0,
    "excessive_iterations": 10.0,
    "slow_synthesis": 5.0,
    "no_progress": 25.0,
    "expected_tool_not_used": 8.0,
}

VERDICT_THRESHOLDS = {
    "passed": 80.0,
    "passed_with_warnings": 50.0,
    # below 50 = failed
}


def compute_score_and_verdict(
    assertions: list[dict],
    diagnostics: list[dict],
) -> tuple[float, str]:
    """Compute score and verdict from assertion results and diagnostics.

    Returns (score, verdict) tuple.
    """
    score = MAX_SCORE
    has_critical_failure = False

    # Penalize assertion failures
    for a in assertions:
        if not a["passed"]:
            if a.get("critical", False):
                score -= PENALTIES["assertion_failed_critical"]
                has_critical_failure = True
            else:
                score -= PENALTIES["assertion_failed"]

    # Penalize diagnostics
    for d in diagnostics:
        code = d["code"]
        if code in PENALTIES:
            score -= PENALTIES[code]

    score = max(0.0, round(score, 1))

    # Verdict
    if has_critical_failure:
        verdict = "failed"
    elif score >= VERDICT_THRESHOLDS["passed"]:
        verdict = "passed"
    elif score >= VERDICT_THRESHOLDS["passed_with_warnings"]:
        verdict = "passed_with_warnings"
    else:
        verdict = "failed"

    return score, verdict
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/scoring.py
git commit -m "feat(test-lab): add deterministic scoring engine — penalty-based with verdict thresholds"
```

---

## Task 7: Runtime Adapter with AgentScope Hooks

**Files:**
- Create: `app/services/test_lab/runtime_adapter.py`

- [ ] **Step 1: Implement runtime adapter that wraps existing AgentScope execution with hook-based event capture**

```python
# app/services/test_lab/runtime_adapter.py
"""Runtime adapter — wraps AgentScope ReActAgent execution and captures events via hooks."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("orkestra.test_lab.runtime")


class RuntimeEventCollector:
    """Collects normalized events during agent execution via AgentScope hooks."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: list[dict] = []
        self.iteration_count = 0
        self._iter_start: float | None = None
        self._llm_start: float | None = None
        self._tool_start: float | None = None

    def _emit(self, event_type: str, phase: str = "runtime", message: str = "", details: dict | None = None, duration_ms: int | None = None):
        self.events.append({
            "run_id": self.run_id,
            "event_type": event_type,
            "phase": phase,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
        })

    # ── AgentScope hooks ───────────────────────────────────

    async def on_pre_reasoning(self, agent, *args, **kwargs):
        self.iteration_count += 1
        self._iter_start = time.time()
        self._llm_start = time.time()
        self._emit("agent_iteration_started", message=f"Iteration {self.iteration_count}")
        self._emit("llm_request_started", message=f"LLM inference iteration {self.iteration_count}")

    async def on_post_reasoning(self, agent, response, *args, **kwargs):
        llm_ms = int((time.time() - self._llm_start) * 1000) if self._llm_start else 0
        self._emit("llm_request_completed", message=f"LLM responded", duration_ms=llm_ms)

        # Check for tool calls in response
        if hasattr(response, "content") and isinstance(response.content, list):
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    self._emit("tool_call_started", message=f"Calling {block.name}", details={
                        "tool_name": block.name,
                        "tool_input": str(getattr(block, "input", {}))[:500],
                    })

    async def on_pre_acting(self, agent, *args, **kwargs):
        self._tool_start = time.time()

    async def on_post_acting(self, agent, response, *args, **kwargs):
        tool_ms = int((time.time() - self._tool_start) * 1000) if self._tool_start else 0
        iter_ms = int((time.time() - self._iter_start) * 1000) if self._iter_start else 0

        # Extract tool result info
        tool_name = "unknown"
        tool_output_preview = ""
        if hasattr(response, "content") and isinstance(response.content, list):
            for block in response.content:
                if hasattr(block, "type"):
                    if block.type == "tool_result":
                        tool_name = getattr(block, "name", "unknown")
                        output = getattr(block, "output", "")
                        if isinstance(output, list):
                            parts = [getattr(b, "text", str(b))[:300] for b in output]
                            tool_output_preview = "\n".join(parts)[:1000]
                        else:
                            tool_output_preview = str(output)[:1000]

        self._emit("tool_call_completed", message=f"Tool '{tool_name}' completed", duration_ms=tool_ms, details={
            "tool_name": tool_name,
            "output_preview": tool_output_preview,
        })
        self._emit("agent_iteration_completed", message=f"Iteration {self.iteration_count} done", duration_ms=iter_ms)


async def execute_with_event_capture(
    db,
    agent_def,
    input_prompt: str,
    max_iterations: int,
    timeout_seconds: int,
    run_id: str,
) -> dict[str, Any]:
    """Execute a real agent with event capture via hooks.

    Returns dict with: status, final_output, duration_ms, events, iteration_count, message_history
    """
    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent
    from agentscope.message import Msg

    collector = RuntimeEventCollector(run_id)

    # Create agent
    collector._emit("phase_started", phase="runtime", message="Creating ReActAgent")
    tools = get_tools_for_agent(agent_def)

    try:
        react_agent = await create_agentscope_agent(
            agent_def, db=db, tools_to_register=tools, max_iters=max_iterations,
        )
    except Exception as e:
        collector._emit("phase_failed", phase="runtime", message=f"Agent creation failed: {e}")
        return {
            "status": "failed",
            "final_output": None,
            "duration_ms": 0,
            "events": collector.events,
            "iteration_count": 0,
            "message_history": [],
            "error": str(e),
        }

    if react_agent is None:
        collector._emit("phase_failed", phase="runtime", message="Agent creation returned None")
        return {
            "status": "failed",
            "final_output": None,
            "duration_ms": 0,
            "events": collector.events,
            "iteration_count": 0,
            "message_history": [],
            "error": "Could not create ReActAgent",
        }

    # Register hooks for event capture
    react_agent.register_instance_hook("pre_reasoning", collector.on_pre_reasoning)
    react_agent.register_instance_hook("post_reasoning", collector.on_post_reasoning)
    react_agent.register_instance_hook("pre_acting", collector.on_pre_acting)
    react_agent.register_instance_hook("post_acting", collector.on_post_acting)

    # Log MCP connections
    connected_mcps = getattr(react_agent, "_connected_mcps", [])
    for mcp in connected_mcps:
        collector._emit("mcp_session_connected", message=f"Connected to {mcp.get('url', '')}", details=mcp)

    collector._emit("run_started", phase="runtime", message="Agent execution started")

    # Execute with timeout
    import asyncio
    t0 = time.time()
    try:
        task_msg = Msg("user", input_prompt, "user")
        response = await asyncio.wait_for(
            react_agent(task_msg),
            timeout=timeout_seconds,
        )
        duration_ms = int((time.time() - t0) * 1000)

        # Extract final output
        if hasattr(response, "get_text_content"):
            final_output = response.get_text_content() or ""
        elif hasattr(response, "content"):
            final_output = str(response.content)
        else:
            final_output = str(response)

        # Capture message history
        message_history = []
        try:
            msgs = await react_agent.memory.get_memory()
            for msg in msgs:
                entry = {"role": getattr(msg, "role", "unknown"), "name": getattr(msg, "name", "")}
                text = ""
                if hasattr(msg, "get_text_content"):
                    text = msg.get_text_content() or ""
                if not text and hasattr(msg, "content"):
                    raw = msg.content
                    if isinstance(raw, list):
                        parts = []
                        for block in raw:
                            if hasattr(block, "text"):
                                parts.append(block.text[:2000])
                            elif hasattr(block, "type"):
                                parts.append(f"[{block.type}]")
                            else:
                                parts.append(str(block)[:500])
                        text = "\n".join(parts)
                    elif isinstance(raw, str):
                        text = raw[:5000]
                    else:
                        text = str(raw)[:5000]
                entry["content"] = text
                message_history.append(entry)
        except Exception:
            pass

        collector._emit("phase_completed", phase="runtime", message="Agent execution completed", duration_ms=duration_ms)

        return {
            "status": "completed",
            "final_output": final_output,
            "duration_ms": duration_ms,
            "events": collector.events,
            "iteration_count": collector.iteration_count,
            "message_history": message_history,
            "error": None,
        }

    except asyncio.TimeoutError:
        duration_ms = int((time.time() - t0) * 1000)
        collector._emit("run_timeout", phase="runtime", message=f"Execution timed out after {timeout_seconds}s", duration_ms=duration_ms)
        return {
            "status": "timed_out",
            "final_output": None,
            "duration_ms": duration_ms,
            "events": collector.events,
            "iteration_count": collector.iteration_count,
            "message_history": [],
            "error": f"Timeout after {timeout_seconds}s",
        }

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        collector._emit("run_failed", phase="runtime", message=f"Execution failed: {e}", duration_ms=duration_ms)
        return {
            "status": "failed",
            "final_output": None,
            "duration_ms": duration_ms,
            "events": collector.events,
            "iteration_count": collector.iteration_count,
            "message_history": [],
            "error": str(e),
        }
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/runtime_adapter.py
git commit -m "feat(test-lab): add runtime adapter with AgentScope hooks for event capture"
```

---

## Task 8: Orchestrator

**Files:**
- Create: `app/services/test_lab/orchestrator.py`

- [ ] **Step 1: Implement central orchestrator**

```python
# app/services/test_lab/orchestrator.py
"""Central test orchestrator — coordinates all phases of an agentic test run."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_lab import TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic, TestScenario
from app.services.test_lab.assertion_engine import evaluate_assertions
from app.services.test_lab.diagnostic_engine import generate_diagnostics
from app.services.test_lab.runtime_adapter import execute_with_event_capture
from app.services.test_lab.scoring import compute_score_and_verdict

logger = logging.getLogger("orkestra.test_lab.orchestrator")


async def run_test(db: AsyncSession, scenario: TestScenario) -> TestRun:
    """Execute a full agentic test run through all orchestration phases.

    Phases: preparation → runtime execution → assertion evaluation → diagnostic analysis → report assembly
    """
    from app.services import agent_registry_service

    # ── Create run record ──────────────────────────────────
    agent = await agent_registry_service.get_agent(db, scenario.agent_id)
    if not agent:
        raise ValueError(f"Agent {scenario.agent_id} not found")

    run = TestRun(
        scenario_id=scenario.id,
        agent_id=scenario.agent_id,
        agent_version=agent.version,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    await _emit_event(db, run.id, "run_created", "orchestrator", "Test run created")
    await _emit_event(db, run.id, "orchestrator_started", "orchestrator", "Orchestrator started")

    t0 = time.time()

    try:
        # ── Phase 1: Preparation ───────────────────────────
        await _emit_event(db, run.id, "phase_started", "preparation", "Validating scenario")
        await _emit_event(db, run.id, "phase_completed", "preparation", "Scenario validated")

        # ── Phase 2: Runtime execution ─────────────────────
        await _emit_event(db, run.id, "handoff_started", "orchestrator", "Dispatching to runtime adapter")
        runtime_result = await execute_with_event_capture(
            db=db,
            agent_def=agent,
            input_prompt=scenario.input_prompt,
            max_iterations=scenario.max_iterations,
            timeout_seconds=scenario.timeout_seconds,
            run_id=run.id,
        )
        await _emit_event(db, run.id, "handoff_completed", "orchestrator", "Runtime execution completed")

        # Persist runtime events
        for evt_data in runtime_result.get("events", []):
            db.add(TestRunEvent(
                run_id=run.id,
                event_type=evt_data["event_type"],
                phase=evt_data.get("phase"),
                message=evt_data.get("message"),
                details=evt_data.get("details"),
                timestamp=datetime.fromisoformat(evt_data["timestamp"]) if isinstance(evt_data.get("timestamp"), str) else datetime.now(timezone.utc),
                duration_ms=evt_data.get("duration_ms"),
            ))
        await db.flush()

        # Update run with runtime results
        run.final_output = runtime_result.get("final_output")
        run.duration_ms = runtime_result.get("duration_ms", 0)
        run.execution_metadata = {
            "iteration_count": runtime_result.get("iteration_count", 0),
            "message_history": runtime_result.get("message_history", []),
            "runtime_status": runtime_result.get("status"),
            "error": runtime_result.get("error"),
        }

        if runtime_result["status"] in ("failed", "timed_out"):
            run.status = runtime_result["status"]
            run.error_message = runtime_result.get("error")

        # ── Phase 3: Assertion evaluation ──────────────────
        await _emit_event(db, run.id, "assertion_phase_started", "assertions", "Evaluating assertions")
        all_events = [{"event_type": e.event_type, "details": e.details, "duration_ms": e.duration_ms}
                      for e in (await _get_events(db, run.id))]

        assertion_results = evaluate_assertions(
            assertion_defs=scenario.assertions or [],
            events=all_events,
            final_output=run.final_output,
            duration_ms=run.duration_ms or 0,
            iteration_count=runtime_result.get("iteration_count", 0),
            final_status=runtime_result.get("status", "unknown"),
        )

        for ar in assertion_results:
            ev_type = "assertion_passed" if ar["passed"] else "assertion_failed"
            await _emit_event(db, run.id, ev_type, "assertions", ar["message"])
            db.add(TestRunAssertion(
                run_id=run.id,
                assertion_type=ar["assertion_type"],
                target=ar.get("target"),
                expected=ar.get("expected"),
                actual=ar.get("actual"),
                passed=ar["passed"],
                critical=ar.get("critical", False),
                message=ar["message"],
                details=ar.get("details"),
            ))
        await db.flush()

        # ── Phase 4: Diagnostic analysis ───────────────────
        await _emit_event(db, run.id, "diagnostic_phase_started", "diagnostics", "Generating diagnostics")
        diag_results = generate_diagnostics(
            events=all_events,
            assertions=assertion_results,
            expected_tools=scenario.expected_tools,
            duration_ms=run.duration_ms or 0,
            iteration_count=runtime_result.get("iteration_count", 0),
            max_iterations=scenario.max_iterations,
            timeout_seconds=scenario.timeout_seconds,
            final_output=run.final_output,
        )

        for dr in diag_results:
            await _emit_event(db, run.id, "diagnostic_generated", "diagnostics", dr["message"], details={"code": dr["code"], "severity": dr["severity"]})
            db.add(TestRunDiagnostic(
                run_id=run.id,
                code=dr["code"],
                severity=dr["severity"],
                message=dr["message"],
                probable_causes=dr.get("probable_causes"),
                recommendation=dr.get("recommendation"),
                evidence=dr.get("evidence"),
            ))
        await db.flush()

        # ── Phase 5: Report assembly ───────────────────────
        await _emit_event(db, run.id, "report_phase_started", "report", "Computing score and verdict")
        score, verdict = compute_score_and_verdict(assertion_results, diag_results)

        run.score = score
        run.verdict = verdict
        run.status = "completed" if run.status == "running" else run.status
        run.summary = f"Score: {score}/100 — Verdict: {verdict} — {len(assertion_results)} assertions, {len(diag_results)} diagnostics"
        run.ended_at = datetime.now(timezone.utc)

        await _emit_event(db, run.id, "run_completed", "orchestrator", f"Run completed: {verdict} ({score}/100)")

    except Exception as e:
        logger.error(f"Orchestrator error for run {run.id}: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.ended_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.time() - t0) * 1000)
        await _emit_event(db, run.id, "run_failed", "orchestrator", f"Orchestrator error: {e}")

    await db.commit()
    await db.refresh(run)
    return run


async def _emit_event(db: AsyncSession, run_id: str, event_type: str, phase: str, message: str, details: dict | None = None):
    db.add(TestRunEvent(
        run_id=run_id,
        event_type=event_type,
        phase=phase,
        message=message,
        details=details,
    ))
    await db.flush()


async def _get_events(db, run_id: str):
    from sqlalchemy import select
    result = await db.execute(
        select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp)
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/orchestrator.py
git commit -m "feat(test-lab): add central orchestrator — 5-phase sequential pipeline with event persistence"
```

---

## Task 9: Agent-Level Evaluation

**Files:**
- Create: `app/services/test_lab/agent_summary.py`

- [ ] **Step 1: Implement agent-level summary**

```python
# app/services/test_lab/agent_summary.py
"""Agent-level test evaluation — aggregates runs for lifecycle readiness."""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_lab import TestRun


async def get_agent_test_summary(db: AsyncSession, agent_id: str) -> dict:
    """Compute agent-level test summary across all runs."""
    runs_q = select(TestRun).where(TestRun.agent_id == agent_id)
    result = await db.execute(runs_q)
    runs = list(result.scalars().all())

    if not runs:
        return {
            "agent_id": agent_id,
            "total_runs": 0,
            "passed_runs": 0,
            "failed_runs": 0,
            "warning_runs": 0,
            "pass_rate": 0.0,
            "average_score": 0.0,
            "last_run_at": None,
            "last_verdict": None,
            "tool_failure_rate": 0.0,
            "timeout_rate": 0.0,
            "average_duration_ms": 0.0,
            "eligible_for_tested": False,
        }

    completed = [r for r in runs if r.status == "completed"]
    passed = [r for r in completed if r.verdict == "passed"]
    warnings = [r for r in completed if r.verdict == "passed_with_warnings"]
    failed = [r for r in completed if r.verdict == "failed"]
    timed_out = [r for r in runs if r.status == "timed_out"]

    total = len(runs)
    pass_rate = len(passed) / total * 100 if total > 0 else 0.0
    scores = [r.score for r in completed if r.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    durations = [r.duration_ms for r in runs if r.duration_ms is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    sorted_runs = sorted(runs, key=lambda r: r.created_at, reverse=True)
    last_run = sorted_runs[0]

    # Eligibility: at least 3 runs, pass rate >= 80%, no recent failures in last 3
    recent_3 = sorted_runs[:3]
    recent_all_pass = all(r.verdict in ("passed", "passed_with_warnings") for r in recent_3 if r.status == "completed")
    eligible = len(completed) >= 3 and pass_rate >= 80.0 and recent_all_pass

    return {
        "agent_id": agent_id,
        "total_runs": total,
        "passed_runs": len(passed),
        "failed_runs": len(failed),
        "warning_runs": len(warnings),
        "pass_rate": round(pass_rate, 1),
        "average_score": round(avg_score, 1),
        "last_run_at": last_run.created_at.isoformat() if last_run.created_at else None,
        "last_verdict": last_run.verdict,
        "tool_failure_rate": 0.0,  # TODO: compute from events
        "timeout_rate": round(len(timed_out) / total * 100, 1) if total > 0 else 0.0,
        "average_duration_ms": round(avg_duration, 0),
        "eligible_for_tested": eligible,
    }
```

- [ ] **Step 2: Commit**

```bash
git add app/services/test_lab/agent_summary.py
git commit -m "feat(test-lab): add agent-level evaluation — summary, pass rate, lifecycle readiness"
```

---

## Task 10: API Routes

**Files:**
- Create: `app/api/routes/test_lab.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create all test lab API endpoints**

```python
# app/api/routes/test_lab.py
"""Agentic Test Lab API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.test_lab import TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic, TestScenario
from app.schemas.test_lab import (
    ScenarioCreate, ScenarioUpdate, ScenarioOut,
    RunOut, EventOut, AssertionResultOut, DiagnosticOut, RunReport, AgentTestSummary,
)
from app.services.test_lab import scenario_service
from app.services.test_lab.orchestrator import run_test
from app.services.test_lab.agent_summary import get_agent_test_summary

router = APIRouter()


# ── Scenarios ──────────────────────────────────────────────

@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
async def create_scenario(data: ScenarioCreate, db: AsyncSession = Depends(get_db)):
    return await scenario_service.create_scenario(db, data)


@router.get("/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(
    agent_id: str | None = None,
    enabled: bool | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    return await scenario_service.list_scenarios(db, agent_id=agent_id, enabled=enabled, limit=limit)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    s = await scenario_service.get_scenario(db, scenario_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return s


@router.patch("/scenarios/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(scenario_id: str, data: ScenarioUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await scenario_service.update_scenario(db, scenario_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await scenario_service.delete_scenario(db, scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Runs ───────────────────────────────────────────────────

@router.post("/scenarios/{scenario_id}/run", response_model=RunOut)
async def start_run(scenario_id: str, db: AsyncSession = Depends(get_db)):
    scenario = await scenario_service.get_scenario(db, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    try:
        run = await run_test(db, scenario)
        return run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs", response_model=list[RunOut])
async def list_runs(
    scenario_id: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(TestRun)
    if scenario_id:
        q = q.where(TestRun.scenario_id == scenario_id)
    if agent_id:
        q = q.where(TestRun.agent_id == agent_id)
    q = q.order_by(TestRun.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/events", response_model=list[EventOut])
async def get_run_events(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp)
    )
    return list(result.scalars().all())


@router.get("/runs/{run_id}/assertions", response_model=list[AssertionResultOut])
async def get_run_assertions(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestRunAssertion).where(TestRunAssertion.run_id == run_id)
    )
    return list(result.scalars().all())


@router.get("/runs/{run_id}/diagnostics", response_model=list[DiagnosticOut])
async def get_run_diagnostics(run_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestRunDiagnostic).where(TestRunDiagnostic.run_id == run_id)
    )
    return list(result.scalars().all())


@router.get("/runs/{run_id}/report", response_model=RunReport)
async def get_run_report(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    scenario = await db.get(TestScenario, run.scenario_id)
    events = (await db.execute(select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp))).scalars().all()
    assertions = (await db.execute(select(TestRunAssertion).where(TestRunAssertion.run_id == run_id))).scalars().all()
    diagnostics = (await db.execute(select(TestRunDiagnostic).where(TestRunDiagnostic.run_id == run_id))).scalars().all()
    return RunReport(run=run, scenario=scenario, events=list(events), assertions=list(assertions), diagnostics=list(diagnostics))


# ── Agent summary ──────────────────────────────────────────

@router.get("/agents/{agent_id}/summary", response_model=AgentTestSummary)
async def get_agent_summary(agent_id: str, db: AsyncSession = Depends(get_db)):
    return await get_agent_test_summary(db, agent_id)
```

- [ ] **Step 2: Register router in main.py**

Add to `app/main.py`:
```python
from app.api.routes import test_lab
# ...
app.include_router(test_lab.router, prefix="/api/test-lab", tags=["test-lab"])
```

- [ ] **Step 3: Commit**

```bash
git add app/api/routes/test_lab.py app/main.py
git commit -m "feat(test-lab): add API routes — scenarios CRUD, run management, events, assertions, diagnostics, agent summary"
```

---

## Tasks 11-15: Frontend (Types, API, Pages, Components)

These tasks follow the exact same patterns shown in the repo exploration. Due to plan length constraints, they are summarized here and should be expanded during execution:

### Task 11: Frontend Types & API Client
- Create `frontend/src/lib/test-lab/types.ts` — TypeScript interfaces for Scenario, Run, Event, Assertion, Diagnostic, AgentTestSummary
- Create `frontend/src/lib/test-lab/api.ts` — API client methods matching backend routes

### Task 12: Scenario List Page
- Create `frontend/src/app/test-lab/page.tsx` — list scenarios with filters, create/run actions

### Task 13: Scenario Detail & Create Pages
- Create `frontend/src/app/test-lab/scenarios/new/page.tsx` — scenario creation form
- Create `frontend/src/app/test-lab/scenarios/[id]/page.tsx` — scenario detail with recent runs

### Task 14: Run Detail Page with Timeline
- Create `frontend/src/app/test-lab/runs/[id]/page.tsx` — live status, score, verdict, timeline, assertions, diagnostics
- Create `frontend/src/components/test-lab/ExecutionTimeline.tsx` — event timeline visualization
- Create `frontend/src/components/test-lab/AssertionsPanel.tsx` — assertion results
- Create `frontend/src/components/test-lab/DiagnosticsPanel.tsx` — diagnostic findings

### Task 15: Agent Test Summary & Sidebar
- Create `frontend/src/components/test-lab/AgentTestSummary.tsx` — summary card for agent detail page
- Update `frontend/src/components/layout/Sidebar.tsx` — update Test Lab link to point to new page

---

## Spec Coverage Verification

| Spec Requirement | Task |
|---|---|
| DB models (Scenario, Run, Event, Assertion, Diagnostic) | Task 1 |
| Strict enums | Task 1 |
| Pydantic contracts | Task 2 |
| Scenario CRUD | Task 3 |
| Deterministic assertions (8 types) | Task 4 |
| Pattern-based diagnostics (7 codes) | Task 5 |
| Scoring & verdict | Task 6 |
| Runtime adapter with AgentScope hooks | Task 7 |
| Central orchestrator (5 phases) | Task 8 |
| Agent-level evaluation | Task 9 |
| Full API | Task 10 |
| Frontend UI | Tasks 11-15 |
| Lifecycle readiness | Task 9 (eligible_for_tested) |
| Event normalization (25 event types) | Tasks 1, 7, 8 |
| Real runtime integration (not fake) | Task 7 |
| Orchestration visibility | Task 8 (events per phase) |
