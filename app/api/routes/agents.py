"""Agent Registry API routes."""

from __future__ import annotations

import logging

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
    OrchestratorGenerationRequest,
    OrchestratorGenerationResponse,
    SaveGeneratedDraftRequest,
)
from app.services import (
    agent_generation_service,
    agent_registry_service,
    agent_test_run_service,
    orchestrator_builder_service,
)
from app.services.test_lab.target_agent_runner import run_target_agent
from sqlalchemy import select

logger = logging.getLogger(__name__)

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


@router.get("")
async def list_agents(
    q: str | None = None,
    family: str | None = None,
    status: str | None = None,
    criticality: str | None = None,
    cost_profile: str | None = None,
    mcp_id: str | None = None,
    workflow_id: str | None = None,
    used_in_workflow_only: bool = False,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    agents, total = await agent_registry_service.list_agents(
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
    items = [await agent_registry_service.enrich_agent(db, a) for a in agents]
    return {"items": items, "total": total, "offset": offset, "limit": limit, "has_more": offset + limit < total}


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
    return AgentGenerationResponse(draft=draft, available_mcps=catalog, source="heuristic_template")


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


@router.post("/generate-orchestrator", response_model=OrchestratorGenerationResponse)
async def generate_orchestrator(
    data: OrchestratorGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an orchestrator agent draft via LLM.

    Manual mode: provide agent_ids (ordered list of ≥2 agent IDs).
    Auto mode: provide use_case_description; LLM selects agents from registry.
    """
    if not data.agent_ids and not data.use_case_description:
        raise HTTPException(
            status_code=400,
            detail="Provide agent_ids (manual mode) or use_case_description (auto mode)",
        )
    try:
        draft, selected_ids = await orchestrator_builder_service.generate_orchestrator(db, data)
        return OrchestratorGenerationResponse(
            draft=draft,
            source="llm",
            selected_agent_ids=selected_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Orchestrator generation failed")
        raise HTTPException(status_code=503, detail="LLM generation failed. Please retry.")


# ── Test Lab ───────────────────────────────────────────────────────────


class TestRunRequest(BaseModel):
    task: str
    structured_input: dict | None = None
    evidence: str | None = None
    context_variables: dict | None = None
    behavioral_checks: list | None = None


@router.post("/{agent_id}/test-run")
async def run_agent_test(
    agent_id: str,
    data: TestRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a behavioral test run against an agent's LLM and persist the result."""
    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    try:
        return await agent_test_run_service.run_test(
            db,
            agent,
            task=data.task,
            structured_input=data.structured_input,
            evidence=data.evidence,
            context_variables=data.context_variables,
            behavioral_checks=data.behavioral_checks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{agent_id}/test-runs")
async def list_agent_test_runs(
    agent_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List persisted test runs for an agent, most recent first."""
    return await agent_test_run_service.list_runs(db, agent_id, limit=limit)


# ── Chat ───────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    timeout_seconds: int = 60
    max_iterations: int = 5


def _synthesize(raw_output: str, user_message: str, tool_calls: list) -> str:
    """Use the LLM to produce a readable French synthesis from the agent's raw output."""
    import json

    # Build context from tool outputs (prefer the richest one)
    tool_context = ""
    for tc in tool_calls:
        out = tc.get("tool_output", "")
        if out and len(out) > 10:
            try:
                parsed = json.loads(out)
                tool_context += f"\n\nTool `{tc.get('tool_name', 'tool')}` returned:\n{json.dumps(parsed, indent=2, ensure_ascii=False)[:4000]}"
            except Exception:
                tool_context += f"\n\nTool `{tc.get('tool_name', 'tool')}` returned:\n{out[:1500]}"

    prompt = (
        f"The user asked: {user_message}\n\n"
        f"The agent's raw result: {raw_output[:1000]}\n"
        f"{tool_context}\n\n"
        "Based on the above, write a clear synthesis IN FRENCH using bullet points. "
        "Include: company name, SIREN/SIRET, siege address, leadership (max 3 directors), "
        "revenue if available, confidence score, resolution status. "
        "Be factual and concise. No code, no JSON, just readable text."
    )

    try:
        from agentscope.message import Msg
        from app.services.test_lab.execution_engine import _make_model, _make_formatter, _run_async

        model = _make_model()
        formatter = _make_formatter()
        msgs = [Msg("user", prompt, "user")]
        formatted = formatter(msgs)
        # Use sync call wrapped in executor to avoid event loop conflicts
        import asyncio, concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            response = pool.submit(model, formatted).result(timeout=30)
        text = response.text if hasattr(response, "text") else str(response)
        return text.strip()
    except Exception:
        return raw_output  # fallback to raw output if synthesis fails


@router.post("/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a chat message to an agent and get a response."""
    result = await run_target_agent(
        db=db,
        agent_id=agent_id,
        agent_version=None,
        input_prompt=body.message,
        timeout_seconds=body.timeout_seconds,
        max_iterations=body.max_iterations,
    )
    if result.status == "failed" and result.error:
        raise HTTPException(status_code=400, detail=result.error)

    # Always synthesize into readable French if there were tool calls
    response_text = result.final_output
    if result.tool_calls:
        import asyncio, concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            response_text = pool.submit(
                _synthesize, result.final_output, body.message, result.tool_calls
            ).result(timeout=35)

    return {
        "response": response_text,
        "raw_output": result.final_output,
        "tool_calls": result.tool_calls,
        "duration_ms": result.duration_ms,
        "status": result.status,
    }
