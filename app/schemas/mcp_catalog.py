"""Schemas for Obot-backed MCP catalog and local Orkestra bindings."""

from datetime import datetime
from typing import Optional, Any

from pydantic import Field

from app.schemas.common import OrkBaseSchema


class ObotServerSummary(OrkBaseSchema):
    id: str
    name: str
    purpose: str
    description: Optional[str] = None
    effect_type: str
    criticality: str
    approval_required: bool = False
    state: str
    health_status: Optional[str] = None
    version: Optional[str] = None
    obot_url: Optional[str] = None


class ObotServerDetails(ObotServerSummary):
    metadata: dict[str, Any] = Field(default_factory=dict)
    usage_last_24h: Optional[int] = None
    incidents_last_7d: Optional[int] = None
    health_note: Optional[str] = None
    mcp_endpoint_url: Optional[str] = None  # remoteConfig.url — used by AgentScope to connect


class OrkestraMcpBinding(OrkBaseSchema):
    obot_server_id: str
    obot_server_name: str
    enabled_in_orkestra: bool = False
    hidden_from_catalog: bool = False
    hidden_from_ai_generator: bool = False
    allowed_agent_families: list[str] = Field(default_factory=list)
    allowed_workflows: list[str] = Field(default_factory=list)
    business_domain: Optional[str] = None
    risk_level_override: Optional[str] = None
    preferred_use_cases: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CatalogMcpViewModel(OrkBaseSchema):
    obot_server: ObotServerSummary
    orkestra_binding: OrkestraMcpBinding
    obot_state: str
    orkestra_state: str
    is_imported_in_orkestra: bool


class CatalogMcpDetailsViewModel(OrkBaseSchema):
    obot_server: ObotServerDetails
    orkestra_binding: OrkestraMcpBinding
    obot_state: str
    orkestra_state: str
    is_imported_in_orkestra: bool


class McpCatalogStats(OrkBaseSchema):
    obot_total: int = 0
    obot_active: int = 0
    obot_degraded: int = 0
    obot_disabled: int = 0
    orkestra_enabled: int = 0
    orkestra_disabled: int = 0
    orkestra_restricted: int = 0
    orkestra_hidden: int = 0
    critical: int = 0
    approval_required: int = 0
    hidden_from_ai_generator: int = 0


class CatalogSyncResult(OrkBaseSchema):
    total_obot_servers: int
    existing_bindings_updated: int
    missing_bindings: int
    source: str


class CatalogImportRequest(OrkBaseSchema):
    obot_server_ids: Optional[list[str]] = None


class CatalogImportResult(OrkBaseSchema):
    imported_count: int
    updated_count: int
    total_selected: int


class OrkestraBindingUpdate(OrkBaseSchema):
    enabled_in_orkestra: Optional[bool] = None
    hidden_from_catalog: Optional[bool] = None
    hidden_from_ai_generator: Optional[bool] = None
    allowed_agent_families: Optional[list[str]] = None
    allowed_workflows: Optional[list[str]] = None
    business_domain: Optional[str] = None
    risk_level_override: Optional[str] = None
    preferred_use_cases: Optional[list[str]] = None
    notes: Optional[str] = None


class BindWorkflowRequest(OrkBaseSchema):
    workflow_id: str = Field(..., min_length=1)


class BindAgentFamilyRequest(OrkBaseSchema):
    agent_family: str = Field(..., min_length=1)
