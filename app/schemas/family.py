"""Family schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.models.enums import FamilyStatus
from app.schemas.common import OrkBaseSchema


class FamilyCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    default_system_rules: list[str] = Field(default_factory=list)
    default_forbidden_effects: list[str] = Field(default_factory=list)
    default_output_expectations: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    status: FamilyStatus = FamilyStatus.active
    owner: Optional[str] = None


class FamilyUpdate(OrkBaseSchema):
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    default_system_rules: Optional[list[str]] = None
    default_forbidden_effects: Optional[list[str]] = None
    default_output_expectations: Optional[list[str]] = None
    version: Optional[str] = None
    status: Optional[FamilyStatus] = None
    owner: Optional[str] = None


class FamilyOut(OrkBaseSchema):
    id: str
    label: str
    description: Optional[str]
    default_system_rules: list[str] = Field(default_factory=list)
    default_forbidden_effects: list[str] = Field(default_factory=list)
    default_output_expectations: list[str] = Field(default_factory=list)
    version: str
    status: FamilyStatus
    owner: Optional[str]
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
