"""Family schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import OrkBaseSchema


class FamilyCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class FamilyUpdate(OrkBaseSchema):
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None


class FamilyOut(OrkBaseSchema):
    id: str
    label: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class FamilyDetail(FamilyOut):
    """Family with associated skills."""
    skills: list["SkillOutBrief"] = Field(default_factory=list)
    agent_count: int = 0


class SkillOutBrief(OrkBaseSchema):
    """Minimal skill info for family detail."""
    skill_id: str
    label: str
    category: str
