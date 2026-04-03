"""Request API routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.request import RequestCreate, RequestOut
from app.services import request_service

router = APIRouter()

@router.post("", response_model=RequestOut, status_code=201)
async def create_request(data: RequestCreate, db: AsyncSession = Depends(get_db)):
    req = await request_service.create_request(db, data)
    return req

@router.get("", response_model=list[RequestOut])
async def list_requests(
    status: str | None = None, criticality: str | None = None,
    use_case: str | None = None, limit: int = 50, offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    return await request_service.list_requests(db, status=status, criticality=criticality,
                                                use_case=use_case, limit=limit, offset=offset)

@router.get("/{request_id}", response_model=RequestOut)
async def get_request(request_id: str, db: AsyncSession = Depends(get_db)):
    req = await request_service.get_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return req

@router.post("/{request_id}/submit", response_model=RequestOut)
async def submit_request(request_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await request_service.submit_request(db, request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
