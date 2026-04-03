"""Supervision API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import supervision_service

router = APIRouter()


@router.get("/runs/{run_id}/live-state")
async def get_run_live_state(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await supervision_service.get_run_live_state(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/metrics/platform")
async def get_platform_metrics(db: AsyncSession = Depends(get_db)):
    return await supervision_service.get_platform_metrics(db)
