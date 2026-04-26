"""Schémas déclaratifs JSON v1 pour import/export GH-14."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter


class BaseDefinitionSchema(BaseModel):
    kind: str
    schema_version: Literal["v1"] = "v1"


class AgentDefinitionSchema(BaseDefinitionSchema):
    kind: Literal["agent"] = "agent"
    id: str
    name: str
    family_id: str
    purpose: str
    description: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    selection_hints: dict[str, Any] | None = None
    allowed_mcps: list[str] = Field(default_factory=list)
    forbidden_effects: list[str] = Field(default_factory=list)
    allow_code_execution: bool = False
    criticality: Literal["low", "medium", "high"]
    cost_profile: Literal["low", "medium", "high", "variable"]
    llm_provider: str | None = None
    llm_model: str | None = None
    limitations: list[str] = Field(default_factory=list)
    prompt_content: str | None = None
    skills_content: str | None = None
    version: str
    status: str


class PipelineStageSchema(BaseModel):
    stage_id: str
    agent_id: str
    required: bool = True


class PipelineDefinitionSchema(BaseModel):
    routing_mode: Literal["sequential", "dynamic"]
    stages: list[PipelineStageSchema] = Field(min_length=1)
    error_policy: Literal["fail_fast", "continue_on_partial_failure", "best_effort"]


class OrchestratorDefinitionSchema(AgentDefinitionSchema):
    kind: Literal["orchestrator"] = "orchestrator"
    pipeline_definition: PipelineDefinitionSchema


class ScenarioDefinitionSchema(BaseDefinitionSchema):
    kind: Literal["scenario"] = "scenario"
    definition_key: str
    name: str
    description: str | None = None
    agent_id: str
    input_prompt: str
    expected_tools: list[str] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    timeout_seconds: int = 120
    max_iterations: int = 10
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


DefinitionPayload = Annotated[
    AgentDefinitionSchema | OrchestratorDefinitionSchema | ScenarioDefinitionSchema,
    Field(discriminator="kind"),
]


_definition_payload_adapter = TypeAdapter(DefinitionPayload)


def validate_definition_payload(payload: dict[str, Any]) -> DefinitionPayload:
    return _definition_payload_adapter.validate_python(payload)
