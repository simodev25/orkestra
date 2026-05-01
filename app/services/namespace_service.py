"""Namespace service — CRUD and namespace resolution helpers."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.namespaces import (
    DEFAULT_NAMESPACE_DESCRIPTION,
    DEFAULT_NAMESPACE_ID,
    DEFAULT_NAMESPACE_NAME,
    DEFAULT_NAMESPACE_SLUG,
)
from app.models.namespace import Namespace
from app.models.registry import AgentDefinition
from app.schemas.namespace import NamespaceCreate, NamespaceUpdate

logger = logging.getLogger("orkestra.namespaces")


async def ensure_default_namespace(db: AsyncSession) -> Namespace:
    default = await get_namespace_by_slug(db, DEFAULT_NAMESPACE_SLUG)
    if default:
        return default

    default = Namespace(
        id=str(DEFAULT_NAMESPACE_ID),
        name=DEFAULT_NAMESPACE_NAME,
        slug=DEFAULT_NAMESPACE_SLUG,
        description=DEFAULT_NAMESPACE_DESCRIPTION,
    )
    db.add(default)
    await db.flush()
    logger.info("namespace_default_ensured", extra={"namespace_id": default.id, "namespace_slug": default.slug})
    return default


async def create_namespace(db: AsyncSession, data: NamespaceCreate) -> Namespace:
    stmt = select(Namespace).where((Namespace.slug == data.slug) | (Namespace.name == data.name))
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise ValueError("Namespace already exists")

    ns = Namespace(name=data.name, slug=data.slug, description=data.description)
    db.add(ns)
    await db.flush()
    logger.info("namespace_created", extra={"namespace_id": ns.id, "namespace_slug": ns.slug})
    return ns


async def list_namespaces(db: AsyncSession, *, offset: int = 0, limit: int = 50) -> tuple[list[Namespace], int]:
    stmt = select(Namespace).order_by(Namespace.slug)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    items = list((await db.execute(stmt.offset(offset).limit(limit))).scalars().all())
    return items, total


async def get_namespace_by_slug(db: AsyncSession, slug: str) -> Namespace | None:
    return (await db.execute(select(Namespace).where(Namespace.slug == slug))).scalar_one_or_none()


async def update_namespace(db: AsyncSession, slug: str, data: NamespaceUpdate) -> Namespace:
    ns = await get_namespace_by_slug(db, slug)
    if not ns:
        raise LookupError("Namespace not found")

    if data.name and data.name != ns.name:
        existing_name = (await db.execute(select(Namespace).where(Namespace.name == data.name))).scalar_one_or_none()
        if existing_name and existing_name.id != ns.id:
            raise ValueError("Namespace already exists")

    updates = data.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(ns, field, value)

    await db.flush()
    logger.info("namespace_updated", extra={"namespace_id": ns.id, "namespace_slug": ns.slug})
    return ns


async def delete_namespace(db: AsyncSession, slug: str) -> None:
    ns = await get_namespace_by_slug(db, slug)
    if not ns:
        raise LookupError("Namespace not found")

    if ns.slug == DEFAULT_NAMESPACE_SLUG:
        raise RuntimeError("Default namespace cannot be deleted")

    ref = await db.execute(select(AgentDefinition.id).where(AgentDefinition.namespace_id == ns.id).limit(1))
    if ref.scalar_one_or_none() is not None:
        raise RuntimeError("Namespace is referenced by agent definitions")

    await db.delete(ns)
    await db.flush()
    logger.info("namespace_deleted", extra={"namespace_id": ns.id, "namespace_slug": ns.slug})
