"""Agent registry schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, Field

from app.schemas.common import OrkBaseSchema
from app.schemas.skill import SkillRef
from app.schemas.family import FamilyOut


class AgentCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    family_id: str = Field(..., min_length=1, max_length=50)
    purpose: str = Field(..., min_length=1)
    description: Optional[str] = None
    skill_ids: Optional[list[str]] = None
    selection_hints: Optional[dict[str, str | list[str] | bool]] = None
    allowed_mcps: Optional[list[str]] = None
    forbidden_effects: Optional[list[str]] = None
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: str = "medium"
    cost_profile: str = "medium"
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    prompt_content: Optional[str] = None
    skills_ref: Optional[str] = None
    skills_content: Optional[str] = None
    soul_content: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    version: str = "1.0.0"
    status: str = "draft"
    owner: Optional[str] = None


class AgentUpdate(OrkBaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    family_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    purpose: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    skill_ids: Optional[list[str]] = None
    selection_hints: Optional[dict[str, str | list[str] | bool]] = None
    allowed_mcps: Optional[list[str]] = None
    forbidden_effects: Optional[list[str]] = None
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: Optional[str] = None
    cost_profile: Optional[str] = None
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    prompt_content: Optional[str] = None
    skills_ref: Optional[str] = None
    skills_content: Optional[str] = None
    soul_content: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    last_test_status: Optional[str] = None
    last_validated_at: Optional[datetime] = None
    usage_count: Optional[int] = None


class AgentOut(OrkBaseSchema):
    id: str
    name: str
    family_id: str
    family: Optional[FamilyOut] = None  # enriched at read time via family_rel
    purpose: str
    description: Optional[str]
    skill_ids: Optional[list[str]] = None  # resolved from agent_skills at read time
    skills_resolved: Optional[list[SkillRef]] = None  # enriched at read time
    selection_hints: Optional[dict[str, str | list[str] | bool]]
    allowed_mcps: Optional[list[str]]
    forbidden_effects: Optional[list[str]]
    input_contract_ref: Optional[str]
    output_contract_ref: Optional[str]
    criticality: str
    cost_profile: str
    limitations: Optional[list[str]]
    prompt_ref: Optional[str]
    prompt_content: Optional[str]
    skills_ref: Optional[str]
    skills_content: Optional[str]
    soul_content: Optional[str]
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    version: str
    status: str
    owner: Optional[str]
    last_test_status: str
    last_validated_at: Optional[datetime]
    usage_count: int
    created_at: datetime
    updated_at: datetime


class AgentStatusUpdate(OrkBaseSchema):
    status: str
    reason: Optional[str] = None


class AgentRegistryStats(OrkBaseSchema):
    total_agents: int
    active_agents: int
    tested_agents: int
    deprecated_agents: int
    current_workflow_agents: int


class McpCatalogSummary(OrkBaseSchema):
    id: str
    name: str
    purpose: str
    effect_type: str
    criticality: str
    approval_required: bool = False
    obot_state: str
    orkestra_state: str


class AgentGenerationRequest(OrkBaseSchema):
    intent: str = Field(..., min_length=10)
    use_case: Optional[str] = None
    target_workflow: Optional[str] = None
    criticality_target: Optional[str] = None
    preferred_family: Optional[str] = None
    preferred_output_style: Optional[str] = None
    preferred_mcp_scope: Optional[str] = None
    constraints: Optional[str] = None
    owner: Optional[str] = None


class GeneratedAgentDraft(OrkBaseSchema):
    agent_id: str = Field(..., validation_alias=AliasChoices("agent_id", "id"))
    name: str
    family_id: str = Field(
        ..., validation_alias=AliasChoices("family_id", "family")
    )
    purpose: str
    description: str
    skill_ids: list[str] = Field(
        default_factory=list, validation_alias=AliasChoices("skill_ids", "skills")
    )
    selection_hints: dict[str, str | list[str] | bool]
    allowed_mcps: list[str]
    forbidden_effects: list[str]
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: str
    cost_profile: str
    limitations: list[str]
    prompt_content: str
    skills_content: str
    owner: Optional[str] = None
    version: str = "1.0.0"
    status: str = "draft"
    suggested_missing_mcps: list[str] = Field(default_factory=list)
    mcp_rationale: dict[str, str] = Field(default_factory=dict)


class AgentGenerationResponse(OrkBaseSchema):
    draft: GeneratedAgentDraft
    available_mcps: list[McpCatalogSummary]
    source: str


class SaveGeneratedDraftRequest(OrkBaseSchema):
    draft: GeneratedAgentDraft
