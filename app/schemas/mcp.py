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


class MCPUpdate(OrkBaseSchema):
    name: Optional[str] = None
    purpose: Optional[str] = None
    description: Optional[str] = None
    effect_type: Optional[str] = None
    input_contract_ref: Optional[str] = None
    output_contract_ref: Optional[str] = None
    allowed_agents: Optional[list[str]] = None
    criticality: Optional[str] = None
    timeout_seconds: Optional[int] = None
    retry_policy: Optional[str] = None
    cost_profile: Optional[str] = None
    approval_required: Optional[bool] = None
    audit_required: Optional[bool] = None
    version: Optional[str] = None
    owner: Optional[str] = None


class MCPHealth(OrkBaseSchema):
    mcp_id: str
    status: str
    healthy: bool
    last_check_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    avg_latency_ms: Optional[float] = None
    failure_rate: Optional[float] = None
    total_invocations: int = 0
    recent_errors: list[str] = []


class MCPUsage(OrkBaseSchema):
    mcp_id: str
    total_invocations: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost: float = 0.0
    agents_using: list[str] = []
    invocations_by_status: dict[str, int] = {}


class MCPCatalogStats(OrkBaseSchema):
    total: int = 0
    active: int = 0
    degraded: int = 0
    disabled: int = 0
    critical: int = 0
    approval_required: int = 0
    healthy: int = 0


class MCPTestRequest(OrkBaseSchema):
    tool_action: Optional[str] = None
    tool_kwargs: dict = {}


class MCPTestResult(OrkBaseSchema):
    mcp_id: str
    success: bool
    latency_ms: int = 0
    output: Optional[str] = None
    error: Optional[str] = None
