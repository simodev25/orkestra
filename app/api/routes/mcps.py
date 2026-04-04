"""MCP Registry API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.mcp import (
    MCPCreate, MCPOut, MCPStatusUpdate,
    MCPUpdate, MCPHealth, MCPUsage, MCPCatalogStats, MCPTestRequest, MCPTestResult,
    MCPValidationReport, MCPValidateRequest,
)
from app.services import mcp_registry_service
from app.services.mcp_validation_engine import validate_mcp, validate_lifecycle_gate

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

# --- catalog-level routes (must come BEFORE /{mcp_id}) ---

@router.get("/catalog/stats", response_model=MCPCatalogStats)
async def get_catalog_stats(db: AsyncSession = Depends(get_db)):
    return await mcp_registry_service.get_catalog_stats(db)

# --- individual MCP routes ---

@router.get("/{mcp_id}", response_model=MCPOut)
async def get_mcp(mcp_id: str, db: AsyncSession = Depends(get_db)):
    mcp = await mcp_registry_service.get_mcp(db, mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    return mcp

@router.put("/{mcp_id}", response_model=MCPOut)
async def update_mcp(mcp_id: str, data: MCPUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.update_mcp(db, mcp_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{mcp_id}/status", response_model=MCPOut)
async def update_mcp_status(mcp_id: str, data: MCPStatusUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.update_mcp_status(db, mcp_id, data.status, data.reason or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{mcp_id}/health", response_model=MCPHealth)
async def get_mcp_health(mcp_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.get_mcp_health(db, mcp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{mcp_id}/usage", response_model=MCPUsage)
async def get_mcp_usage(mcp_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.get_mcp_usage(db, mcp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{mcp_id}/validate", response_model=MCPValidationReport)
async def validate_mcp_endpoint(
    mcp_id: str,
    data: MCPValidateRequest = MCPValidateRequest(),
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await validate_mcp(db, mcp_id, include_integration=data.include_integration)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{mcp_id}/validate-gate/{target_status}", response_model=MCPValidationReport)
async def validate_gate_endpoint(
    mcp_id: str,
    target_status: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await validate_lifecycle_gate(db, mcp_id, target_status)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{mcp_id}/test", response_model=MCPTestResult)
async def test_mcp(mcp_id: str, data: MCPTestRequest = MCPTestRequest(), db: AsyncSession = Depends(get_db)):
    try:
        return await mcp_registry_service.test_mcp(db, mcp_id, data.tool_action, data.tool_kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
