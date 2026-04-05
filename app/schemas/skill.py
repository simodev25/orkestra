"""Skill schemas — first-class skill definitions sourced from skills.seed.json."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

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


class SkillOut(OrkBaseSchema):
    """Full skill as exposed by the API."""

    skill_id: str
    label: str
    category: str
    description: str
    behavior_templates: list[str]
    output_guidelines: list[str]


class AgentSummary(OrkBaseSchema):
    """Minimal agent info for skill->agents listing."""

    agent_id: str
    label: str


class SkillWithAgents(OrkBaseSchema):
    """Skill enriched with the list of agents that use it."""

    skill_id: str
    label: str
    category: str
    description: str
    agents: list[AgentSummary]


class SkillSeedEntry(OrkBaseSchema):
    """Schema for a single entry in skills.seed.json."""

    skill_id: str
    label: str
    category: str
    description: str
    behavior_templates: list[str] = Field(..., min_length=1)
    output_guidelines: list[str] = Field(..., min_length=1)

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
