"""Case API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.case import CaseOut
from app.services import case_service

router = APIRouter()

@router.get("", response_model=list[CaseOut])
async def list_cases(
    status: str | None = None, criticality: str | None = None,
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db),
):
    return await case_service.list_cases(db, status=status, criticality=criticality, limit=limit, offset=offset)

@router.get("/{case_id}", response_model=CaseOut)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    case = await case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@router.post("/{request_id}/convert", response_model=CaseOut, status_code=201)
async def convert_request_to_case(request_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await case_service.convert_request_to_case(db, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
