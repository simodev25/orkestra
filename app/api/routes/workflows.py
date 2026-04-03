"""Workflow API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowOut
from app.services import workflow_service

router = APIRouter()


@router.post("", response_model=WorkflowOut, status_code=201)
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await workflow_service.create_workflow(
            db, data.name, data.use_case, data.execution_mode,
            data.graph_definition, data.policy_profile_id, data.budget_profile_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    use_case: str | None = None, status: str | None = None,
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db),
):
    return await workflow_service.list_workflows(db, use_case=use_case, status=status, limit=limit, offset=offset)


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    wf = await workflow_service.get_workflow(db, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.put("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(workflow_id: str, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await workflow_service.update_workflow(db, workflow_id, **data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/validate")
async def validate_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await workflow_service.validate_workflow(db, workflow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/publish", response_model=WorkflowOut)
async def publish_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await workflow_service.publish_workflow(db, workflow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
