"""Agent registry schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import re

from pydantic import AliasChoices, Field, field_validator

from app.models.enums import AgentStatus, Criticality, CostProfile
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
    criticality: Criticality = Criticality.MEDIUM
    cost_profile: CostProfile = CostProfile.MEDIUM
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    prompt_content: Optional[str] = None
    skills_ref: Optional[str] = None
    skills_content: Optional[str] = None
    soul_content: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    allow_code_execution: bool = False
    allowed_builtin_tools: Optional[list[str]] = None
    pipeline_agent_ids: Optional[list[str]] = None
    routing_mode: str = "sequential"
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.DRAFT
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
    criticality: Optional[Criticality] = None
    cost_profile: Optional[CostProfile] = None
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    prompt_content: Optional[str] = None
    skills_ref: Optional[str] = None
    skills_content: Optional[str] = None
    soul_content: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    allow_code_execution: Optional[bool] = None
    allowed_builtin_tools: Optional[list[str]] = None
    pipeline_agent_ids: Optional[list[str]] = None
    routing_mode: Optional[str] = None
    version: Optional[str] = None
    status: Optional[AgentStatus] = None
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
    criticality: Criticality
    cost_profile: CostProfile
    limitations: Optional[list[str]]
    prompt_ref: Optional[str]
    prompt_content: Optional[str]
    skills_ref: Optional[str]
    skills_content: Optional[str]
    soul_content: Optional[str]
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    allow_code_execution: bool = False
    allowed_builtin_tools: Optional[list[str]] = None
    pipeline_agent_ids: Optional[list[str]] = None
    routing_mode: str = "sequential"
    version: str
    status: AgentStatus
    owner: Optional[str]
    last_test_status: str
    last_validated_at: Optional[datetime]
    usage_count: int
    created_at: datetime
    updated_at: datetime


class AgentStatusUpdate(OrkBaseSchema):
    status: AgentStatus
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
    preferred_skill_ids: Optional[list[str]] = None
    preferred_output_style: Optional[str] = None
    preferred_mcp_scope: Optional[str] = None
    constraints: Optional[str] = None
    owner: Optional[str] = None

    @field_validator("intent")
    @classmethod
    def _validate_intent(cls, value: str) -> str:
        sanitized = re.sub(r"[\x00-\x1F\x7F]", " ", value)
        sanitized = " ".join(sanitized.split()).strip()
        if len(sanitized) > 2000:
            raise ValueError("intent must be at most 2000 characters")
        return sanitized

    @field_validator("constraints")
    @classmethod
    def _validate_constraints(cls, value: str | None) -> str | None:
        if value is None:
            return None
        sanitized = re.sub(r"[\x00-\x1F\x7F]", " ", value)
        sanitized = " ".join(sanitized.split()).strip()
        if len(sanitized) > 2000:
            raise ValueError("constraints must be at most 2000 characters")
        return sanitized


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
    criticality: Criticality
    cost_profile: CostProfile
    limitations: list[str]
    prompt_content: str
    skills_content: str
    owner: Optional[str] = None
    version: str = "1.0.0"
    status: AgentStatus = AgentStatus.DRAFT
    suggested_missing_mcps: list[str] = Field(default_factory=list)
    mcp_rationale: dict[str, str] = Field(default_factory=dict)
    pipeline_agent_ids: list[str] = Field(default_factory=list)
    routing_mode: str = "sequential"


class AgentGenerationResponse(OrkBaseSchema):
    draft: GeneratedAgentDraft
    available_mcps: list[McpCatalogSummary]
    source: str


class SaveGeneratedDraftRequest(OrkBaseSchema):
    draft: GeneratedAgentDraft


class OrchestratorGenerationRequest(OrkBaseSchema):
    """Request body for POST /generate-orchestrator."""
    name: str = Field(..., min_length=3, description="snake_case id for the orchestrator")
    agent_ids: list[str] = Field(
        default_factory=list,
        description="Ordered list of agent IDs (manual mode). Empty = auto mode.",
    )
    use_case_description: Optional[str] = Field(
        None,
        description="Free-text pipeline description (auto mode). LLM selects agents.",
    )
    user_instructions: Optional[str] = Field(
        None,
        description="Extra context/priorities/constraints passed to LLM in both modes.",
    )
    routing_strategy: str = Field(default="sequential", description="Pipeline execution strategy. Currently only 'sequential' is supported.")


class OrchestratorGenerationResponse(OrkBaseSchema):
    """Response from POST /generate-orchestrator."""
    draft: GeneratedAgentDraft
    source: str = Field("llm", description="Origin of the draft: 'llm'.")
    selected_agent_ids: list[str] = Field(
        default_factory=list,
        description="Agent IDs picked by the LLM (populated in auto mode).",
    )
