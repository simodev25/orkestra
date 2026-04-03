"""Workflow schemas."""

from datetime import datetime
from typing import Optional, Any
from pydantic import Field
from app.schemas.common import OrkBaseSchema


class WorkflowCreate(OrkBaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    use_case: Optional[str] = None
    execution_mode: str = "sequential"
    graph_definition: Optional[dict[str, Any]] = None
    policy_profile_id: Optional[str] = None
    budget_profile_id: Optional[str] = None


class WorkflowUpdate(OrkBaseSchema):
    name: Optional[str] = None
    execution_mode: Optional[str] = None
    graph_definition: Optional[dict[str, Any]] = None
    policy_profile_id: Optional[str] = None
    budget_profile_id: Optional[str] = None


class WorkflowOut(OrkBaseSchema):
    id: str
    name: str
    version: str
    use_case: Optional[str]
    execution_mode: str
    graph_definition: Optional[dict[str, Any]]
    policy_profile_id: Optional[str]
    budget_profile_id: Optional[str]
    status: str
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
