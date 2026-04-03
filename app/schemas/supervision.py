"""Supervision schemas."""

from typing import Optional, Any

from app.schemas.common import OrkBaseSchema


class RunLiveState(OrkBaseSchema):
    run_id: str
    run_status: str
    started_at: Optional[str]
    estimated_cost: Optional[float]
    actual_cost: float
    nodes_total: int
    nodes_by_status: dict[str, int]
    nodes: list[dict[str, Any]]
    agent_invocations: int
    agent_invocations_cost: float
    mcp_invocations: int
    mcp_invocations_cost: float
    control_decisions: int
    control_denials: int


class PlatformMetrics(OrkBaseSchema):
    runs_by_status: dict[str, int]
    total_runs: int
    total_agent_cost: float
    total_mcp_cost: float
    total_cost: float
    control_decisions_by_type: dict[str, int]
    audit_events_total: int
