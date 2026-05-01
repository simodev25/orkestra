"""Namespace request-scoped dependencies."""

from __future__ import annotations

import logging

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.namespaces import DEFAULT_NAMESPACE_SLUG, NAMESPACE_SLUG_RE
from app.models.namespace import Namespace
from app.services.namespace_service import ensure_default_namespace, get_namespace_by_slug

logger = logging.getLogger("orkestra.namespaces")


async def get_resolved_namespace(
    request: Request,
    x_namespace: str | None = Header(default=None, alias="X-Namespace"),
    db: AsyncSession = Depends(get_db),
) -> Namespace:
    raw_header_value = x_namespace
    namespace_slug = (x_namespace or "").strip() or DEFAULT_NAMESPACE_SLUG
    resolution_source = "default_fallback" if not (x_namespace or "").strip() else "header"

    if not NAMESPACE_SLUG_RE.match(namespace_slug):
        logger.warning(
            "namespace_resolution_failed",
            extra={
                "event": "namespace_resolution_failed",
                "namespace_slug": namespace_slug,
                "raw_header_value": raw_header_value,
                "failure_reason": "invalid_slug",
                "resolution_source": resolution_source,
                "http_method": request.method,
                "request_path": str(request.url.path),
            },
        )
        raise HTTPException(status_code=422, detail="Invalid namespace slug")

    namespace = await get_namespace_by_slug(db, namespace_slug)
    if not namespace and resolution_source == "default_fallback" and namespace_slug == DEFAULT_NAMESPACE_SLUG:
        namespace = await ensure_default_namespace(db)

    if not namespace:
        logger.warning(
            "namespace_resolution_failed",
            extra={
                "event": "namespace_resolution_failed",
                "namespace_slug": namespace_slug,
                "raw_header_value": raw_header_value,
                "failure_reason": "not_found",
                "resolution_source": resolution_source,
                "http_method": request.method,
                "request_path": str(request.url.path),
            },
        )
        raise HTTPException(status_code=404, detail="Namespace not found")

    return namespace
