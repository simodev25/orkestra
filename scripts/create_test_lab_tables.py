"""Create test lab tables directly in PostgreSQL."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import get_settings


STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS test_scenarios (
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
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_scenarios_agent_id ON test_scenarios (agent_id)",
    """CREATE TABLE IF NOT EXISTS test_runs (
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
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_runs_scenario_id ON test_runs (scenario_id)",
    "CREATE INDEX IF NOT EXISTS ix_test_runs_agent_id ON test_runs (agent_id)",
    """CREATE TABLE IF NOT EXISTS test_run_events (
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
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_run_events_run_id ON test_run_events (run_id)",
    """CREATE TABLE IF NOT EXISTS test_run_assertions (
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
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_run_assertions_run_id ON test_run_assertions (run_id)",
    """CREATE TABLE IF NOT EXISTS test_run_diagnostics (
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
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_run_diagnostics_run_id ON test_run_diagnostics (run_id)",
]


async def create():
    engine = create_async_engine(get_settings().DATABASE_URL)
    async with engine.begin() as conn:
        for sql in STATEMENTS:
            await conn.execute(text(sql))
    await engine.dispose()
    print("All test lab tables created")


asyncio.run(create())
