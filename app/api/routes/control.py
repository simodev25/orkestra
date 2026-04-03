"""Control decisions API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.control import ControlDecisionOut
from app.services import control_service

router = APIRouter()


@router.get("/control-decisions", response_model=list[ControlDecisionOut])
async def list_decisions(
    decision_scope: str | None = None,
    decision_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await control_service.list_decisions(
        db, decision_scope=decision_scope, decision_type=decision_type,
        limit=limit, offset=offset,
    )


@router.get("/runs/{run_id}/control-decisions", response_model=list[ControlDecisionOut])
async def get_run_decisions(run_id: str, db: AsyncSession = Depends(get_db)):
    return await control_service.get_decisions_for_run(db, run_id)
