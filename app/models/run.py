"""Run and RunNode entities."""

from datetime import datetime

from sqlalchemy import String, Float, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id
from app.models.enums import RunStatus, RunNodeStatus, RunNodeType


class Run(BaseModel):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("run_"))
    case_id: Mapped[str] = mapped_column(String(36))
    plan_id: Mapped[str] = mapped_column(String(36))
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=RunStatus.CREATED)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cost: Mapped[float] = mapped_column(Float, default=0.0)
    approval_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    replay_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    final_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class RunNode(BaseModel):
    __tablename__ = "run_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("node_"))
    run_id: Mapped[str] = mapped_column(String(36))
    node_type: Mapped[str] = mapped_column(String(30), default=RunNodeType.SUBAGENT)
    node_ref: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default=RunNodeStatus.PENDING)
    depends_on: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parallel_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trigger_condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
