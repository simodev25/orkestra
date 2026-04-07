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

    # Launch test in background
    run_id = run.id
    scenario_id_copy = scenario.id

    async def _run_in_background():
        from app.core.database import get_async_session_factory
        factory = get_async_session_factory()
        async with factory() as bg_db:
            bg_scenario = await scenario_service.get_scenario(bg_db, scenario_id_copy)
            if bg_scenario:
                await run_test(bg_db, bg_scenario, existing_run_id=run_id)

    asyncio.get_event_loop().create_task(_run_in_background())

    return {"id": run.id, "status": "queued", "scenario_id": scenario.id, "agent_id": scenario.agent_id}


@router.get("/runs/{run_id}/stream")
async def stream_run_events(run_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint — polls DB for new events and streams them live."""
    run = await db.get(TestRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_count = 0
        while True:
            result = await db.execute(
                select(TestRunEvent).where(TestRunEvent.run_id == run_id).order_by(TestRunEvent.timestamp)
            )
            events = list(result.scalars().all())

            if len(events) > last_count:
                for evt in events[last_count:]:
                    data = json.dumps({
                        "id": evt.id,
                        "event_type": evt.event_type,
                        "phase": evt.phase,
                        "message": evt.message,
                        "details": evt.details,
                        "timestamp": evt.timestamp.isoformat() if evt.timestamp else None,
                        "duration_ms": evt.duration_ms,
                    })
                    yield f"data: {data}\n\n"
                last_count = len(events)

            # Check if run is terminal
            await db.refresh(run)
            if run.status in ("completed", "failed", "timed_out", "cancelled"):
                # Send final status
                yield f"data: {json.dumps({'event_type': 'stream_end', 'status': run.status, 'verdict': run.verdict, 'score': run.score, 'summary': run.summary})}\n\n"
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
