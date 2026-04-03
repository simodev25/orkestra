"""Audit & Replay API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.audit import AuditEventOut, EvidenceRecordOut, ReplayBundleOut
from app.services import audit_service

router = APIRouter()


@router.get("/runs/{run_id}/audit", response_model=list[AuditEventOut])
async def get_audit_trail(run_id: str, db: AsyncSession = Depends(get_db)):
    return await audit_service.get_audit_trail(db, run_id)


@router.get("/runs/{run_id}/evidence", response_model=list[EvidenceRecordOut])
async def get_evidence(run_id: str, db: AsyncSession = Depends(get_db)):
    return await audit_service.get_evidence_for_run(db, run_id)


@router.post("/runs/{run_id}/replay-bundle", response_model=ReplayBundleOut, status_code=201)
async def generate_replay_bundle(run_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await audit_service.generate_replay_bundle(db, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs/{run_id}/replay-bundle", response_model=ReplayBundleOut)
async def get_replay_bundle(run_id: str, db: AsyncSession = Depends(get_db)):
    bundle = await audit_service.get_replay_bundle(db, run_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Replay bundle not found")
    return bundle
