"""Agent Registry API routes."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.family import AgentSkill
from app.schemas.agent import (
    AgentCreate,
    AgentGenerationRequest,
    AgentGenerationResponse,
    AgentOut,
    AgentRegistryStats,
    AgentStatusUpdate,
    AgentUpdate,
    McpCatalogSummary,
    SaveGeneratedDraftRequest,
)
from app.services import agent_generation_service, agent_registry_service
from app.services.agent_test_service import execute_test_run
from sqlalchemy import select

router = APIRouter()


@router.get("/stats", response_model=AgentRegistryStats)
async def get_agent_registry_stats(
    workflow_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await agent_registry_service.get_registry_stats(db, workflow_id=workflow_id)


@router.get("/available-skills")
async def get_available_skills(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentSkill.skill_id).distinct())
    return sorted(row[0] for row in result.all())


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    try:
        agent = await agent_registry_service.create_agent(db, data)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[AgentOut])
async def list_agents(
    q: str | None = None,
    family: str | None = None,
    status: str | None = None,
    criticality: str | None = None,
    cost_profile: str | None = None,
    mcp_id: str | None = None,
    workflow_id: str | None = None,
    used_in_workflow_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    agents = await agent_registry_service.list_agents(
        db,
        q=q,
        family=family,
        status=status,
        criticality=criticality,
        cost_profile=cost_profile,
        mcp_id=mcp_id,
        workflow_id=workflow_id,
        used_in_workflow_only=used_in_workflow_only,
        limit=limit,
        offset=offset,
    )
    return [await agent_registry_service.enrich_agent(db, a) for a in agents]


@router.get("/llm-models/{provider}")
async def list_llm_models(provider: str, db: AsyncSession = Depends(get_db)):
    """Fetch available models from the LLM provider API."""
    import httpx
    from app.core.config import get_settings
    from app.services.secret_service import get_secret
    settings = get_settings()

    if provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("https://ollama.com/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"provider": "ollama", "models": sorted(models)}
        except Exception as e:
            return {"provider": "ollama", "models": [], "error": str(e)}

    elif provider == "openai":
        api_key = await get_secret(db, "OPENAI_API_KEY", settings.OPENAI_API_KEY)
        base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        if not api_key:
            return {"provider": "openai", "models": [], "error": "OPENAI_API_KEY not configured. Set it in Admin > Security."}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                resp.raise_for_status()
                data = resp.json()
                models = sorted([m["id"] for m in data.get("data", [])])
                return {"provider": "openai", "models": models}
        except Exception as e:
            return {"provider": "openai", "models": [], "error": str(e)}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


@router.get("/{agent_id}/history")
async def get_agent_history(agent_id: str, db: AsyncSession = Depends(get_db)):
    history = await agent_registry_service.get_agent_history(db, agent_id)
    return [
        {
            "id": h.id,
            "agent_id": h.agent_id,
            "name": h.name,
            "family_id": h.family_id,
            "purpose": h.purpose,
            "skill_ids_snapshot": h.skill_ids_snapshot,
            "version": h.version,
            "status": h.status,
            "owner": h.owner,
            "criticality": h.criticality,
            "replaced_at": h.replaced_at.isoformat(),
        }
        for h in history
    ]


@router.post("/{agent_id}/restore/{history_id}", response_model=AgentOut)
async def restore_agent(agent_id: str, history_id: str, db: AsyncSession = Depends(get_db)):
    try:
        agent = await agent_registry_service.restore_agent(db, agent_id, history_id)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await agent_registry_service.enrich_agent(db, agent)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    try:
        agent = await agent_registry_service.update_agent(db, agent_id, data)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        exc_str = str(exc)
        if "not allowed for family" in exc_str or "skills not allowed" in exc_str:
            raise HTTPException(status_code=422, detail=exc_str)
        raise HTTPException(status_code=400, detail=exc_str)


@router.patch("/{agent_id}/status", response_model=AgentOut)
async def update_agent_status(
    agent_id: str,
    data: AgentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        agent = await agent_registry_service.update_agent_status(db, agent_id, data.status, data.reason or "")
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    existing = await agent_registry_service.get_agent(db, agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        await agent_registry_service.delete_agent(db, agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/generate-draft", response_model=AgentGenerationResponse)
async def generate_agent_draft(
    data: AgentGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    available = await agent_registry_service.available_mcp_summaries(db)
    catalog = [McpCatalogSummary.model_validate(item) for item in available]
    draft = agent_generation_service.generate_agent_draft(data, catalog)
    return AgentGenerationResponse(draft=draft, available_mcps=catalog, source="mock_llm")


@router.post("/save-generated-draft", response_model=AgentOut, status_code=201)
async def save_generated_draft(
    data: SaveGeneratedDraftRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        agent = await agent_registry_service.save_generated_draft(db, data.draft)
        return await agent_registry_service.enrich_agent(db, agent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Test Lab ───────────────────────────────────────────────────────────


class TestRunRequest(BaseModel):
    task: str
    structured_input: Optional[dict] = None
    evidence: Optional[str] = None
    context_variables: Optional[dict] = None
    behavioral_checks: Optional[list] = None


@router.post("/{agent_id}/test-run")
async def run_agent_test(
    agent_id: str,
    data: TestRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a behavioral test run against an agent's LLM and persist the result."""
    from app.models.agent_test_run import AgentTestRun

    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    result = await execute_test_run(
        db,
        agent,
        task=data.task,
        structured_input=data.structured_input,
        evidence=data.evidence,
        context_variables=data.context_variables,
    )

    is_error = result.get("status") == "error"
    verdict = "error" if is_error else "pass"

    # Record Prometheus metrics
    from app.api.routes.metrics import AGENT_TEST_RUNS, AGENT_TEST_LATENCY, AGENT_TEST_TOKENS
    AGENT_TEST_RUNS.labels(agent_id=agent_id, verdict=verdict).inc()
    AGENT_TEST_LATENCY.labels(agent_id=agent_id).observe(result.get("latency_ms", 0))
    token_usage = result.get("token_usage")
    if token_usage:
        AGENT_TEST_TOKENS.labels(agent_id=agent_id, type="input").inc(token_usage.get("input", 0))
        AGENT_TEST_TOKENS.labels(agent_id=agent_id, type="output").inc(token_usage.get("output", 0))

    # Build metadata with full context for detail view
    from app.services.prompt_builder import build_agent_prompt
    from app.services.agent_factory import get_tools_for_agent
    from app.models.family import AgentSkill
    from app.models.skill import SkillDefinition

    try:
        system_prompt = await build_agent_prompt(db, agent, runtime_context=data.context_variables)
    except Exception:
        system_prompt = ""

    tools = get_tools_for_agent(agent)

    # Resolve skills from DB
    skill_result = await db.execute(
        select(SkillDefinition)
        .join(AgentSkill, AgentSkill.skill_id == SkillDefinition.id)
        .where(AgentSkill.agent_id == agent_id)
    )
    skills_resolved = [
        {"skill_id": s.id, "label": s.label, "category": s.category, "description": s.description}
        for s in skill_result.scalars().all()
    ]

    # Resolve MCP details from catalog
    mcp_details = []
    try:
        catalog_mcps = await agent_registry_service.available_mcp_summaries(db)
        mcp_map = {m["id"]: m for m in catalog_mcps}
    except Exception:
        mcp_map = {}
    for mcp_id in (agent.allowed_mcps or []):
        cat = mcp_map.get(mcp_id)
        if cat:
            mcp_details.append({
                "id": mcp_id,
                "name": cat.get("name", mcp_id),
                "purpose": cat.get("purpose", ""),
                "effect_type": cat.get("effect_type", ""),
                "criticality": cat.get("criticality", ""),
                "orkestra_state": cat.get("orkestra_state", "unknown"),
            })
        else:
            mcp_details.append({"id": mcp_id, "name": mcp_id, "orkestra_state": "not_found"})

    trace_meta = {
        "system_prompt": system_prompt,
        "agent_name": agent.name,
        "family_id": agent.family_id,
        "purpose": agent.purpose,
        "allowed_mcps": agent.allowed_mcps or [],
        "mcp_details": mcp_details,
        "forbidden_effects": agent.forbidden_effects or [],
        "tools": [f.__name__ for f in tools],
        "skills": skills_resolved,
        "limitations": agent.limitations or [],
        "criticality": agent.criticality,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "prompt_ref": agent.prompt_ref,
    }

    # Persist the run in DB
    run = AgentTestRun(
        agent_id=agent_id,
        agent_version=agent.version,
        status=result.get("status", "error"),
        verdict="error" if is_error else "pending",
        latency_ms=result.get("latency_ms", 0),
        provider=result.get("provider"),
        model=result.get("model"),
        raw_output=result.get("raw_output", ""),
        task=data.task,
        token_usage=result.get("token_usage"),
        behavioral_checks=data.behavioral_checks,
        error_message=result.get("error") if is_error else None,
        trace_data=trace_meta,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Save debug JSON file
    import os
    from pathlib import Path
    from datetime import datetime, timezone

    debug_dir = Path(os.environ.get("ORKESTRA_DEBUG_STRATEGY_DIR", "/app/storage/debug-strategy"))
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = run.created_at.strftime("%Y%m%d_%H%M%S") if run.created_at else datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    debug_filename = f"{agent_id}_test_{verdict}_v{agent.version}_{ts}.json"
    debug_payload = {
        "schema_version": 1,
        "type": "agent_test_run",
        "run_id": run.id,
        "generated_at": run.created_at.isoformat() if run.created_at else None,
        "status": run.status,
        "verdict": verdict,
        "elapsed_ms": result.get("latency_ms", 0),
        "agent": {
            "id": agent_id,
            "name": agent.name,
            "version": agent.version,
            "family_id": agent.family_id,
            "purpose": agent.purpose,
            "criticality": agent.criticality,
            "cost_profile": agent.cost_profile,
        },
        "llm": {
            "provider": result.get("provider"),
            "model": result.get("model"),
        },
        "prompts": {
            "system_prompt": system_prompt,
            "user_task": data.task,
            "user_prompt": result.get("user_prompt", ""),
            "structured_input": data.structured_input,
            "evidence": data.evidence,
            "context_variables": data.context_variables,
        },
        "tools": {
            "allowed_mcps": agent.allowed_mcps or [],
            "mcp_details": mcp_details,
            "forbidden_effects": agent.forbidden_effects or [],
            "registered_tools": [f.__name__ for f in tools],
            "connected_mcps": result.get("connected_mcps", []),
        },
        "skills": skills_resolved,
        "limitations": agent.limitations or [],
        "result": {
            "raw_output": result.get("raw_output", ""),
            "user_prompt": result.get("user_prompt", ""),
            "token_usage": result.get("token_usage"),
            "error": result.get("error"),
        },
        "behavioral_checks": data.behavioral_checks,
        "message_history": result.get("message_history", []),
    }
    try:
        with open(debug_dir / debug_filename, "w") as f:
            json.dump(debug_payload, f, indent=2, default=str)
    except Exception:
        pass

    return {
        "id": run.id,
        "agent_id": agent_id,
        "agent_version": agent.version,
        "created_at": run.created_at.isoformat(),
        "debug_file": debug_filename,
        **result,
    }


@router.get("/{agent_id}/test-runs")
async def list_agent_test_runs(
    agent_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List persisted test runs for an agent, most recent first."""
    from app.models.agent_test_run import AgentTestRun

    result = await db.execute(
        select(AgentTestRun)
        .where(AgentTestRun.agent_id == agent_id)
        .order_by(AgentTestRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
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
            "raw_output": r.raw_output,
            "task": r.task,
            "token_usage": r.token_usage,
            "behavioral_checks": r.behavioral_checks,
            "error_message": r.error_message,
            "metadata": r.trace_data,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]
