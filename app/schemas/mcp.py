"""MCP registry schemas."""

from pydantic import Field
from datetime import datetime
from typing import Optional

from app.schemas.common import OrkBaseSchema


class MCPCreate(OrkBaseSchema):
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    purpose: str = Field(..., min_length=1)
    description: Optional[str] = None
    effect_type: str = Field(..., min_length=1)
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    allowed_agents: Optional[list[str]] = None
    criticality: str = "medium"
    timeout_seconds: int = 30
    retry_policy: str = "standard"
    cost_profile: str = "low"
    approval_required: bool = False
    audit_required: bool = True
    version: str = "1.0.0"
    owner: Optional[str] = None


class MCPOut(OrkBaseSchema):
    id: str
    name: str
    purpose: str
    description: Optional[str]
    effect_type: str
    allowed_agents: Optional[list[str]]
    criticality: str
    timeout_seconds: int
    retry_policy: str
    cost_profile: str
    approval_required: bool
    audit_required: bool
    status: str
    version: str
    owner: Optional[str]
    created_at: datetime
    updated_at: datetime


class MCPStatusUpdate(OrkBaseSchema):
    status: str
    reason: Optional[str] = None
