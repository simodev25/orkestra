"""ControlDecision entity."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id


class ControlDecision(BaseModel):
    __tablename__ = "control_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("cd_"))
    run_id: Mapped[str] = mapped_column(String(36))
    decision_scope: Mapped[str] = mapped_column(String(30))
    decision_type: Mapped[str] = mapped_column(String(30))
    policy_rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    target_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
