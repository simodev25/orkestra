# app/api/routes/test_lab.py
"""Agentic Test Lab API routes."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.test_lab import TestRun, TestRunEvent, TestRunAssertion, TestRunDiagnostic, TestScenario
from app.schemas.test_lab import (
    ScenarioCreate, ScenarioUpdate, ScenarioOut,
    RunOut, EventOut, AssertionResultOut, DiagnosticOut, RunReport, AgentTestSummary,
    TestLabConfig,
)
from app.services.test_lab import scenario_service
from app.services.test_lab.orchestrator import run_test
from app.services.test_lab.agent_summary import get_agent_test_summary

router = APIRouter()


# ── Scenarios ──────────────────────────────────────────────

@router.post("/scenarios", response_model=ScenarioOut, status_code=201)
async def create_scenario(data: ScenarioCreate, db: AsyncSession = Depends(get_db)):
    return await scenario_service.create_scenario(db, data)


@router.get("/scenarios")
async def list_scenarios(
    agent_id: str | None = None,
    enabled: bool | None = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    items, total = await scenario_service.list_scenarios(db, agent_id=agent_id, enabled=enabled, offset=offset, limit=limit)
    return {"items": items, "total": total, "offset": offset, "limit": limit, "has_more": offset + limit < total}


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

@router.post("/scenarios/{scenario_id}/run")
async def start_run(scenario_id: str, db: AsyncSession = Depends(get_db)):
    """Start a test run asynchronously. Returns immediately with run ID."""
    from app.services import agent_registry_service

    scenario = await scenario_service.get_scenario(db, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    agent = await agent_registry_service.get_agent(db, scenario.agent_id)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent {scenario.agent_id} not found")

    # Create run record immediately
    from datetime import datetime, timezone
    run = TestRun(
        scenario_id=scenario.id, agent_id=scenario.agent_id, agent_version=agent.version,
        status="queued", started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Dispatch to Celery worker
    from app.tasks.test_lab import run_test_task
    run_test_task.delay(run.id, scenario.id)

    return {"id": run.id, "status": "queued", "scenario_id": scenario.id, "agent_id": scenario.agent_id}


@router.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint — subscribes to Redis pub/sub for real-time events."""
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        import redis.asyncio as aioredis
        from app.core.config import get_settings

        r = aioredis.from_url(get_settings().REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"test_lab:run:{run_id}")

        try:
            # First, send any existing events from DB
            result = await db.execute(
                select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp)
            )
            for evt in result.scalars().all():
                data = json.dumps({
                    "id": evt.id, "event_type": evt.event_type, "phase": evt.phase,
                    "message": evt.message, "details": evt.details,
                    "timestamp": evt.timestamp.isoformat() if evt.timestamp else None,
                    "duration_ms": evt.duration_ms,
                })
                yield f"data: {data}\n\n"

            # Then stream new events from Redis pub/sub
            while True:
                msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0), timeout=120)
                if msg and msg["type"] == "message":
                    event = json.loads(msg["data"])
                    yield f"data: {json.dumps(event)}\n\n"

                    # Check if run completed
                    if event.get("event_type") in ("run_completed", "run_failed", "run_timeout"):
                        await db.refresh(run)
                        yield f"data: {json.dumps({'event_type': 'stream_end', 'status': run.status, 'verdict': run.verdict, 'score': run.score, 'summary': run.summary})}\n\n"
                        break
        except asyncio.TimeoutError:
            # Stream timed out — send final status
            await db.refresh(run)
            yield f"data: {json.dumps({'event_type': 'stream_end', 'status': run.status, 'verdict': run.verdict, 'score': run.score, 'summary': run.summary})}\n\n"
        finally:
            await pubsub.unsubscribe(f"test_lab:run:{run_id}")
            await r.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/runs")
async def list_runs(
    scenario_id: str | None = None,
    agent_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func as sa_func
    base_q = select(TestRun)
    if scenario_id:
        base_q = base_q.where(TestRun.scenario_id == scenario_id)
    if agent_id:
        base_q = base_q.where(TestRun.agent_id == agent_id)
    count_result = await db.execute(select(sa_func.count()).select_from(base_q.subquery()))
    total = count_result.scalar() or 0
    paged_q = base_q.order_by(TestRun.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(paged_q)
    items = list(result.scalars().all())
    return {"items": items, "total": total, "offset": offset, "limit": limit, "has_more": offset + limit < total}


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


# ── Configuration ─────────────────────────────────────────

DEFAULT_CONFIG = {
    "orchestrator": {
        "provider": "ollama",
        "model": "gpt-oss:20b-cloud",
        "max_iters": 10,
    },
    "workers": {
        "preparation": {
            "prompt": "You are a test preparation agent. Produce a structured TEST PLAN: Objective, Target agent, Input, Expected behavior, Assertions, Constraints, Risks. Be concise.",
            "model": None,
            "skills": [],
        },
        "assertion": {
            "prompt": "Analyze assertion results briefly.",
            "model": None,
            "skills": [],
        },
        "diagnostic": {
            "prompt": "Analyze diagnostic findings and recommend fixes.",
            "model": None,
            "skills": [],
        },
        "verdict": {
            "prompt": "Produce a concise final test summary.",
            "model": None,
            "skills": [],
        },
    },
    "defaults": {
        "timeout_seconds": 120,
        "max_iterations": 5,
        "retry_count": 0,
    },
}


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db)):
    """Get test lab configuration."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT key, value FROM test_lab_config"))
    rows = {r[0]: r[1] for r in result.fetchall()}
    config = {**DEFAULT_CONFIG}
    for key in config:
        if key in rows:
            if isinstance(config[key], dict):
                config[key] = {**config[key], **rows[key]}
            else:
                config[key] = rows[key]
    return config


@router.get("/config/skills")
async def list_available_skills(db: AsyncSession = Depends(get_db)):
    """List all available skills from the registry."""
    from app.models.skill import SkillDefinition
    result = await db.execute(select(SkillDefinition).order_by(SkillDefinition.category, SkillDefinition.label))
    return [
        {"id": s.id, "label": s.label, "category": s.category, "description": s.description,
         "behavior_templates": s.behavior_templates, "output_guidelines": s.output_guidelines}
        for s in result.scalars().all()
    ]


@router.get("/config/models/{provider}")
async def list_models(provider: str):
    """List available models from Ollama or OpenAI."""
    import httpx

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("https://ollama.com/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = [{"name": m["name"], "size": m.get("size", 0)} for m in data.get("models", [])]
                return {"provider": "ollama", "models": models}
        except Exception as e:
            return {"provider": "ollama", "models": [], "error": str(e)}

    elif provider == "openai":
        from app.core.config import get_settings
        from app.services.secret_service import get_secret
        from app.core.database import get_async_session_factory
        settings = get_settings()
        factory = get_async_session_factory()
        async with factory() as db_session:
            api_key = await get_secret(db_session, "OPENAI_API_KEY", settings.OPENAI_API_KEY)
        base_url = (settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        if not api_key:
            return {"provider": "openai", "models": [], "error": "API key not configured"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
                resp.raise_for_status()
                data = resp.json()
                models = [{"name": m["id"], "size": 0} for m in data.get("data", [])]
                return {"provider": "openai", "models": sorted(models, key=lambda m: m["name"])}
        except Exception as e:
            return {"provider": "openai", "models": [], "error": str(e)}

    return {"provider": provider, "models": [], "error": f"Unknown provider: {provider}"}


@router.put("/config")
async def update_config(data: TestLabConfig, db: AsyncSession = Depends(get_db)):
    """Update test lab configuration."""
    from sqlalchemy import text
    config_dict = data.model_dump(exclude_none=True)
    for key, value in config_dict.items():
        await db.execute(text(
            "INSERT INTO test_lab_config (key, value, updated_at) VALUES (:key, :val, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = :val, updated_at = NOW()"
        ), {"key": key, "val": json.dumps(value)})
    await db.commit()
    return await get_config(db)
