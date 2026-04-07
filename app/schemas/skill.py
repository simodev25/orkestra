"""Skill schemas — first-class skill definitions sourced from skills.seed.json."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, Field, field_validator

from app.models.enums import SkillStatus
from app.schemas.common import OrkBaseSchema


class SkillContent(OrkBaseSchema):
    """The actual skill payload consumed by agents."""

    description: str
    behavior_templates: list[str] = Field(..., min_length=1)
    output_guidelines: list[str] = Field(..., min_length=1)


class SkillRef(OrkBaseSchema):
    """Minimal skill reference used in AgentOut.skills_resolved."""

    skill_id: str
    label: str
    category: str
    skills_content: SkillContent


class SkillCreate(OrkBaseSchema):
    """Schema for creating a new skill via the API."""

    id: str = Field(default=None, min_length=1, max_length=100, validation_alias=AliasChoices("id", "skill_id"))
    label: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    behavior_templates: list[str] = Field(default_factory=list)
    output_guidelines: list[str] = Field(default_factory=list)
    allowed_families: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    status: SkillStatus = SkillStatus.active
    owner: Optional[str] = None


class SkillUpdate(OrkBaseSchema):
    """Schema for partial-updating a skill via the API."""

    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    behavior_templates: Optional[list[str]] = None
    output_guidelines: Optional[list[str]] = None
    allowed_families: Optional[list[str]] = None
    version: Optional[str] = None
    status: Optional[SkillStatus] = None
    owner: Optional[str] = None


class SkillOut(OrkBaseSchema):
    """Full skill as exposed by the API."""

    skill_id: str
    label: str
    category: str
    description: Optional[str]
    behavior_templates: list[str]
    output_guidelines: list[str]
    allowed_families: list[str] = Field(default_factory=list)
    version: Optional[str] = None
    status: Optional[SkillStatus] = None
    owner: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AgentSummary(OrkBaseSchema):
    """Minimal agent info for skill->agents listing."""

    agent_id: str
    label: str


class SkillWithAgents(OrkBaseSchema):
    """Skill enriched with the list of agents that use it."""

    skill_id: str
    label: str
    category: str
    description: Optional[str] = None
    behavior_templates: list[str] = Field(default_factory=list)
    output_guidelines: list[str] = Field(default_factory=list)
    allowed_families: list[str] = Field(default_factory=list)
    version: Optional[str] = None
    status: Optional[SkillStatus] = None
    owner: Optional[str] = None
    agents: list[AgentSummary]


class SkillSeedEntry(OrkBaseSchema):
    """Schema for a single entry in skills.seed.json."""

    skill_id: str
    label: str
    category: str
    description: str
    behavior_templates: list[str] = Field(..., min_length=1)
    output_guidelines: list[str] = Field(..., min_length=1)
    allowed_families: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    status: SkillStatus = SkillStatus.active
    owner: Optional[str] = None

    @field_validator("behavior_templates", "output_guidelines")
    @classmethod
    def reject_empty_lists(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("must be a non-empty list")
        return v


class SkillSeedPayload(OrkBaseSchema):
    """Root schema for skills.seed.json."""

    schema_version: int = Field(default=1)
    skills: list[SkillSeedEntry] = Field(..., min_length=1)
