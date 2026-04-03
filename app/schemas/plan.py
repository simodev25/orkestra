"""Plan API schemas."""

from datetime import datetime
from typing import Optional, Any

from app.schemas.common import OrkBaseSchema


class PlanOut(OrkBaseSchema):
    id: str
    case_id: str
    run_id: Optional[str]
    workflow_id: Optional[str]
    objective_summary: Optional[str]
    selected_agents: Optional[list[Any]]
    selected_mcps: Optional[list[Any]]
    execution_topology: Optional[dict]
    estimated_cost: Optional[float]
    estimated_parallelism: Optional[int]
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
