"""Approval API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.approval import ApprovalCreate, ApprovalOut, ApprovalDecision, ApprovalAssign
from app.services import approval_service

router = APIRouter()


@router.post("", response_model=ApprovalOut, status_code=201)
async def create_approval(data: ApprovalCreate, db: AsyncSession = Depends(get_db)):
    return await approval_service.create_approval(
        db, data.run_id, data.case_id, data.approval_type, data.reason, data.reviewer_role)


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status: str | None = None, run_id: str | None = None,
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db),
):
    return await approval_service.list_approvals(db, status=status, run_id=run_id, limit=limit, offset=offset)


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    a = await approval_service.get_approval(db, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    return a


@router.post("/{approval_id}/assign", response_model=ApprovalOut)
async def assign_reviewer(approval_id: str, data: ApprovalAssign, db: AsyncSession = Depends(get_db)):
    try:
        return await approval_service.assign_reviewer(db, approval_id, data.assigned_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{approval_id}/approve", response_model=ApprovalOut)
async def approve(approval_id: str, data: ApprovalDecision = ApprovalDecision(), db: AsyncSession = Depends(get_db)):
    try:
        return await approval_service.approve(db, approval_id, data.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{approval_id}/reject", response_model=ApprovalOut)
async def reject(approval_id: str, data: ApprovalDecision = ApprovalDecision(), db: AsyncSession = Depends(get_db)):
    try:
        return await approval_service.reject(db, approval_id, data.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{approval_id}/refine", response_model=ApprovalOut)
async def request_refinement(approval_id: str, data: ApprovalDecision = ApprovalDecision(), db: AsyncSession = Depends(get_db)):
    try:
        return await approval_service.request_refinement(db, approval_id, data.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
