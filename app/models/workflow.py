"""WorkflowDefinition entity."""

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id


class WorkflowDefinition(BaseModel):
    __tablename__ = "workflow_definitions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=lambda: new_id("wf_"))
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    use_case: Mapped[str | None] = mapped_column(String(100), nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(30), default="sequential")
    graph_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    policy_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    budget_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    published_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
