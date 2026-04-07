"""Create test lab tables directly in PostgreSQL.

Usage:
  python scripts/create_test_lab_tables.py

Uses ORKESTRA_DATABASE_URL env var if set, otherwise defaults to
the Docker Compose dev database (localhost:5434).
"""

import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


DEFAULT_URL = "postgresql+asyncpg://orkestra:orkestra@localhost:5434/orkestra"


STATEMENTS = [
    # ── test_scenarios ────────────────────────────────────────────────────
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

    # ── test_runs ─────────────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS test_runs (
        id VARCHAR(36) PRIMARY KEY,
        scenario_id VARCHAR(36),
        agent_id VARCHAR(100) NOT NULL,
        agent_version VARCHAR(20),
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
    "CREATE INDEX IF NOT EXISTS ix_test_runs_status ON test_runs (status)",

    # ── test_run_events ───────────────────────────────────────────────────
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
    "CREATE INDEX IF NOT EXISTS ix_test_run_events_event_type ON test_run_events (event_type)",

    # ── test_run_assertions ───────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS test_run_assertions (
        id VARCHAR(36) PRIMARY KEY,
        run_id VARCHAR(36) NOT NULL,
        assertion_type VARCHAR(50) NOT NULL,
        target VARCHAR(255),
        expected TEXT,
        actual TEXT,
        passed BOOLEAN NOT NULL,
        critical BOOLEAN DEFAULT FALSE,
        message TEXT,
        details JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_run_assertions_run_id ON test_run_assertions (run_id)",

    # ── test_run_diagnostics ──────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS test_run_diagnostics (
        id VARCHAR(36) PRIMARY KEY,
        run_id VARCHAR(36) NOT NULL,
        code VARCHAR(50) NOT NULL,
        severity VARCHAR(20) NOT NULL,
        message TEXT,
        probable_causes JSONB,
        recommendation TEXT,
        evidence JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_test_run_diagnostics_run_id ON test_run_diagnostics (run_id)",

    # ── agent_test_runs ───────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS agent_test_runs (
        id VARCHAR(36) PRIMARY KEY,
        agent_id VARCHAR(100) NOT NULL,
        agent_version VARCHAR(20),
        status VARCHAR(20),
        verdict VARCHAR(20),
        latency_ms INTEGER,
        provider VARCHAR(50),
        model VARCHAR(100),
        raw_output TEXT,
        task TEXT,
        token_usage JSON,
        behavioral_checks JSON,
        error_message TEXT,
        trace_data JSON,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_agent_test_runs_agent_id ON agent_test_runs (agent_id)",
    "CREATE INDEX IF NOT EXISTS ix_agent_test_runs_status ON agent_test_runs (status)",
    "CREATE INDEX IF NOT EXISTS ix_agent_test_runs_created_at ON agent_test_runs (created_at)",

    # ── test_lab_config (key-value store) ─────────────────────────────────
    """CREATE TABLE IF NOT EXISTS test_lab_config (
        key VARCHAR(100) PRIMARY KEY,
        value TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
]


async def create():
    db_url = os.environ.get("ORKESTRA_DATABASE_URL", DEFAULT_URL)
    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else db_url}")

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        for sql in STATEMENTS:
            await conn.execute(text(sql))
    await engine.dispose()

    print(f"Done — {len(STATEMENTS)} statements executed (all tables + indexes created)")


if __name__ == "__main__":
    asyncio.run(create())
