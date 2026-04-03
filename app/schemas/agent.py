"""Agent registry schemas."""

from pydantic import Field
from datetime import datetime
from typing import Optional

from app.schemas.common import OrkBaseSchema


class AgentCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    family: str = Field(..., min_length=1, max_length=50)
    purpose: str = Field(..., min_length=1)
    description: Optional[str] = None
    skills: Optional[list[str]] = None
    selection_hints: Optional[dict] = None
    allowed_mcps: Optional[list[str]] = None
    forbidden_effects: Optional[list[str]] = None
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    criticality: str = "medium"
    cost_profile: str = "medium"
    limitations: Optional[list[str]] = None
    prompt_ref: Optional[str] = None
    skills_ref: Optional[str] = None
    version: str = "1.0.0"
    owner: Optional[str] = None


class AgentOut(OrkBaseSchema):
    id: str
    name: str
    family: str
    purpose: str
    description: Optional[str]
    skills: Optional[list[str]]
    selection_hints: Optional[dict]
    allowed_mcps: Optional[list[str]]
    forbidden_effects: Optional[list[str]]
    criticality: str
    cost_profile: str
    limitations: Optional[list[str]]
    prompt_ref: Optional[str]
    skills_ref: Optional[str]
    version: str
    status: str
    owner: Optional[str]
    created_at: datetime
    updated_at: datetime


class AgentStatusUpdate(OrkBaseSchema):
    status: str
    reason: Optional[str] = None
