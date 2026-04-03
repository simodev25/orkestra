"""Run API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.run import RunCreate, RunOut, RunNodeOut
from app.services import execution_service

router = APIRouter()


@router.post("/cases/{case_id}/runs", response_model=RunOut, status_code=201)
async def create_run(case_id: str, data: RunCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await execution_service.create_run(db, case_id, data.plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/start", response_model=RunOut)
async def start_run(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await execution_service.start_run(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs", response_model=list[RunOut])
async def list_runs(
    case_id: str | None = None, status: str | None = None,
    limit: int = 50, offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await execution_service.list_runs(db, case_id=case_id, status=status, limit=limit, offset=offset)


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await execution_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/nodes", response_model=list[RunNodeOut])
async def get_run_nodes(run_id: str, db: AsyncSession = Depends(get_db)):
    return await execution_service.get_run_nodes(db, run_id)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await execution_service.cancel_run(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
