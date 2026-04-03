"""Plan API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.plan import PlanOut
from app.services import orchestrator_service

router = APIRouter()


@router.post("/cases/{case_id}/plan", response_model=PlanOut, status_code=201)
async def generate_plan(case_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await orchestrator_service.generate_plan(db, case_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plans/{plan_id}", response_model=PlanOut)
async def get_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    plan = await orchestrator_service.get_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan
