"""OrchestrationPlan entity."""

from sqlalchemy import String, Text, Float, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id
from app.models.enums import PlanStatus


class OrchestrationPlan(BaseModel):
    __tablename__ = "orchestration_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("plan_"))
    case_id: Mapped[str] = mapped_column(String(36))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    objective_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_agents: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    selected_mcps: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    execution_topology: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_parallelism: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=PlanStatus.DRAFT)
    created_by: Mapped[str] = mapped_column(String(100), default="orchestrator")
