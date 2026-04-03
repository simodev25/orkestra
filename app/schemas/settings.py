"""Settings schemas."""

from typing import Optional, Any
from pydantic import Field
from app.schemas.common import OrkBaseSchema
from datetime import datetime


class PolicyProfileCreate(OrkBaseSchema):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    rules: Optional[dict[str, Any]] = None
    is_default: bool = False


class PolicyProfileOut(OrkBaseSchema):
    id: str
    name: str
    description: Optional[str]
    rules: Optional[dict[str, Any]]
    is_default: bool
    created_at: datetime
    updated_at: datetime


class BudgetProfileCreate(OrkBaseSchema):
    name: str = Field(..., min_length=1)
    max_run_cost: Optional[float] = None
    max_agent_cost: Optional[float] = None
    max_mcp_cost: Optional[float] = None
    soft_limit: Optional[float] = None
    hard_limit: Optional[float] = None
    is_default: bool = False


class BudgetProfileOut(OrkBaseSchema):
    id: str
    name: str
    max_run_cost: Optional[float]
    max_agent_cost: Optional[float]
    max_mcp_cost: Optional[float]
    soft_limit: Optional[float]
    hard_limit: Optional[float]
    is_default: bool
    created_at: datetime
    updated_at: datetime
