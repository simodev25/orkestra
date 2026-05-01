"""Namespace API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.namespace import NamespaceCreate, NamespaceRead, NamespaceUpdate
from app.services import namespace_service

router = APIRouter()


@router.post("", response_model=NamespaceRead, status_code=201)
async def create_namespace(data: NamespaceCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await namespace_service.create_namespace(db, data)
    except ValueError:
        raise HTTPException(status_code=409, detail="Namespace already exists")


@router.get("")
async def list_namespaces(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    items, total = await namespace_service.list_namespaces(db, offset=offset, limit=limit)
    return {"items": items, "total": total, "offset": offset, "limit": limit, "has_more": offset + limit < total}


@router.get("/{slug}", response_model=NamespaceRead)
async def get_namespace(slug: str, db: AsyncSession = Depends(get_db)):
    ns = await namespace_service.get_namespace_by_slug(db, slug)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return ns


@router.put("/{slug}", response_model=NamespaceRead)
async def update_namespace(slug: str, data: NamespaceUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await namespace_service.update_namespace(db, slug, data)
    except LookupError:
        raise HTTPException(status_code=404, detail="Namespace not found")
    except ValueError:
        raise HTTPException(status_code=409, detail="Namespace already exists")


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_namespace(slug: str, db: AsyncSession = Depends(get_db)):
    if slug == "default":
        raise HTTPException(status_code=409, detail="Default namespace cannot be deleted")
    try:
        await namespace_service.delete_namespace(db, slug)
    except LookupError:
        raise HTTPException(status_code=404, detail="Namespace not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
