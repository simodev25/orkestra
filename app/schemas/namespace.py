"""Namespace schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.namespaces import NAMESPACE_SLUG_PATTERN
from app.schemas.common import OrkBaseSchema


class NamespaceCreate(OrkBaseSchema):
    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., pattern=NAMESPACE_SLUG_PATTERN)
    description: str | None = None


class NamespaceUpdate(OrkBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class NamespaceRead(OrkBaseSchema):
    id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime
