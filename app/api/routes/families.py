"""Family API routes — CRUD for agent families."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.family import FamilyCreate, FamilyDetail, FamilyOut, FamilyUpdate
from app.services import family_service

router = APIRouter()


@router.get("", response_model=list[FamilyOut])
async def list_families(
    include_archived: bool = Query(False, alias="include_archived"),
    db: AsyncSession = Depends(get_db),
):
    return await family_service.list_families(db, include_archived=include_archived)


@router.get("/{family_id}", response_model=FamilyDetail)
async def get_family(family_id: str, db: AsyncSession = Depends(get_db)):
    detail = await family_service.get_family_detail(db, family_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Family '{family_id}' not found")
    return detail


@router.post("", response_model=FamilyOut, status_code=201)
async def create_family(data: FamilyCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await family_service.create_family(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{family_id}/archive", response_model=FamilyOut)
async def archive_family(family_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await family_service.archive_family(db, family_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{family_id}", response_model=FamilyOut)
async def update_family(family_id: str, data: FamilyUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await family_service.update_family(db, family_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{family_id}", response_model=FamilyOut | None)
async def delete_family(family_id: str, db: AsyncSession = Depends(get_db)):
    """Delete (if unreferenced) or archive (if referenced) the family.

    Returns 200 with archived family body when references exist, 204 when hard-deleted.
    """
    try:
        result = await family_service.delete_family(db, family_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if result is not None:
        # Was archived — return 200 with the family body
        return result
    return Response(status_code=status.HTTP_204_NO_CONTENT)
