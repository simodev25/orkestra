"""Approval schemas."""

from datetime import datetime
from typing import Optional
from app.schemas.common import OrkBaseSchema


class ApprovalCreate(OrkBaseSchema):
    run_id: str
    case_id: str
    approval_type: str
    reason: str
    reviewer_role: Optional[str] = None


class ApprovalOut(OrkBaseSchema):
    id: str
    run_id: str
    case_id: str
    approval_type: str
    reason: str
    reviewer_role: Optional[str]
    assigned_to: Optional[str]
    status: str
    requested_at: Optional[datetime]
    resolved_at: Optional[datetime]
    decision_comment: Optional[str]
    created_at: datetime
    updated_at: datetime


class ApprovalDecision(OrkBaseSchema):
    comment: str = ""


class ApprovalAssign(OrkBaseSchema):
    assigned_to: str
