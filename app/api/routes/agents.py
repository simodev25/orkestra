"""Agent Registry API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.agent import AgentCreate, AgentOut, AgentStatusUpdate
from app.services import agent_registry_service

router = APIRouter()

@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await agent_registry_service.create_agent(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=list[AgentOut])
async def list_agents(
    family: str | None = None, status: str | None = None,
    criticality: str | None = None, limit: int = 50, offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await agent_registry_service.list_agents(db, family=family, status=status,
                                                     criticality=criticality, limit=limit, offset=offset)

@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    agent = await agent_registry_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.patch("/{agent_id}/status", response_model=AgentOut)
async def update_agent_status(agent_id: str, data: AgentStatusUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await agent_registry_service.update_agent_status(db, agent_id, data.status, data.reason or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
