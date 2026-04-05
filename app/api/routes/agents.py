"""Agent Registry API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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

router = APIRouter()


@router.get("/stats", response_model=AgentRegistryStats)
async def get_agent_registry_stats(
    workflow_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await agent_registry_service.get_registry_stats(db, workflow_id=workflow_id)


@router.get("/available-skills")
async def get_available_skills(db: AsyncSession = Depends(get_db)):
    return await agent_registry_service.available_skills(db)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await agent_registry_service.create_agent(db, data)
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
    return await agent_registry_service.list_agents(
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


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent_registry_service.enrich_agent_skills(agent)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: str, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await agent_registry_service.update_agent(db, agent_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{agent_id}/status", response_model=AgentOut)
async def update_agent_status(
    agent_id: str,
    data: AgentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await agent_registry_service.update_agent_status(db, agent_id, data.status, data.reason or "")
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
        return await agent_registry_service.save_generated_draft(db, data.draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
