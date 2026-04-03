"""Run API schemas."""

from datetime import datetime
from typing import Optional, Any

from app.schemas.common import OrkBaseSchema


class RunCreate(OrkBaseSchema):
    plan_id: str


class RunOut(OrkBaseSchema):
    id: str
    case_id: str
    plan_id: str
    workflow_id: Optional[str]
    status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    estimated_cost: Optional[float]
    actual_cost: float
    approval_state: Optional[str]
    replay_status: Optional[str]
    final_output: Optional[dict]
    created_at: datetime
    updated_at: datetime


class RunNodeOut(OrkBaseSchema):
    id: str
    run_id: str
    node_type: str
    node_ref: str
    status: str
    depends_on: Optional[list[str]]
    parallel_group: Optional[str]
    order_index: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
