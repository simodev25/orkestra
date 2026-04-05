"""Obot-backed MCP Catalog API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.mcp_catalog import (
    BindAgentFamilyRequest,
    BindWorkflowRequest,
    CatalogImportRequest,
    CatalogImportResult,
    CatalogMcpDetailsViewModel,
    CatalogMcpViewModel,
    CatalogSyncResult,
    McpCatalogStats,
    OrkestraBindingUpdate,
    OrkestraMcpBinding,
)
from app.services import obot_catalog_service

router = APIRouter()


@router.get("", response_model=list[CatalogMcpViewModel])
async def list_mcp_catalog(
    search: str | None = None,
    obot_status: str | None = None,
    orkestra_status: str | None = None,
    criticality: str | None = None,
    effect_type: str | None = None,
    approval_required: bool | None = None,
    allowed_workflow: str | None = None,
    allowed_agent_family: str | None = None,
    hidden_from_ai_generator: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await obot_catalog_service.list_catalog_items(
        db,
        search=search,
        obot_status=obot_status,
        orkestra_status=orkestra_status,
        criticality=criticality,
        effect_type=effect_type,
        approval_required=approval_required,
        allowed_workflow=allowed_workflow,
        allowed_agent_family=allowed_agent_family,
        hidden_from_ai_generator=hidden_from_ai_generator,
    )


@router.get("/stats", response_model=McpCatalogStats)
async def get_mcp_catalog_stats(db: AsyncSession = Depends(get_db)):
    return await obot_catalog_service.get_catalog_stats(db)


@router.post("/sync", response_model=CatalogSyncResult)
async def sync_mcp_catalog(db: AsyncSession = Depends(get_db)):
    return await obot_catalog_service.sync_obot_catalog(db)


@router.post("/import", response_model=CatalogImportResult)
async def import_mcp_catalog(
    request: CatalogImportRequest = CatalogImportRequest(),
    db: AsyncSession = Depends(get_db),
):
    return await obot_catalog_service.import_from_obot(db, request.obot_server_ids)


@router.get("/{obot_server_id}", response_model=CatalogMcpDetailsViewModel)
async def get_mcp_catalog_item(obot_server_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await obot_catalog_service.get_catalog_item(db, obot_server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{obot_server_id}/bindings", response_model=OrkestraMcpBinding)
async def update_mcp_bindings(
    obot_server_id: str,
    payload: OrkestraBindingUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await obot_catalog_service.update_orkestra_binding(db, obot_server_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{obot_server_id}/enable", response_model=OrkestraMcpBinding)
async def enable_mcp_in_orkestra(obot_server_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await obot_catalog_service.enable_in_orkestra(db, obot_server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{obot_server_id}/disable", response_model=OrkestraMcpBinding)
async def disable_mcp_in_orkestra(obot_server_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await obot_catalog_service.disable_in_orkestra(db, obot_server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{obot_server_id}/bind-workflow", response_model=OrkestraMcpBinding)
async def bind_mcp_to_workflow(
    obot_server_id: str,
    payload: BindWorkflowRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await obot_catalog_service.bind_to_workflow(db, obot_server_id, payload.workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{obot_server_id}/bind-agent-family", response_model=OrkestraMcpBinding)
async def bind_mcp_to_agent_family(
    obot_server_id: str,
    payload: BindAgentFamilyRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await obot_catalog_service.bind_to_agent_family(
            db, obot_server_id, payload.agent_family
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
