"""MCP Registry API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.mcp import MCPCreate, MCPOut, MCPStatusUpdate
from app.services import mcp_registry_service

router = APIRouter()

@router.post("", response_model=MCPOut, status_code=201)
async def create_mcp(data: MCPCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.create_mcp(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=list[MCPOut])
async def list_mcps(
    effect_type: str | None = None, status: str | None = None,
    criticality: str | None = None, limit: int = 50, offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await mcp_registry_service.list_mcps(db, effect_type=effect_type, status=status,
                                                 criticality=criticality, limit=limit, offset=offset)

@router.get("/{mcp_id}", response_model=MCPOut)
async def get_mcp(mcp_id: str, db: AsyncSession = Depends(get_db)):
    mcp = await mcp_registry_service.get_mcp(db, mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    return mcp

@router.patch("/{mcp_id}/status", response_model=MCPOut)
async def update_mcp_status(mcp_id: str, data: MCPStatusUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.update_mcp_status(db, mcp_id, data.status, data.reason or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
