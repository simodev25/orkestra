"""Control decision schemas."""

from datetime import datetime
from typing import Optional

from app.schemas.common import OrkBaseSchema


class ControlDecisionOut(OrkBaseSchema):
    id: str
    run_id: str
    decision_scope: str
    decision_type: str
    policy_rule_id: Optional[str]
    reason: str
    severity: str
    target_ref: Optional[str]
    created_at: datetime
    updated_at: datetime
