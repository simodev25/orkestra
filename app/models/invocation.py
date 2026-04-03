"""SubagentInvocation and MCPInvocation entities."""

from sqlalchemy import String, Text, Float, DateTime, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id


class SubagentInvocation(BaseModel):
    __tablename__ = "subagent_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("sai_"))
    run_id: Mapped[str] = mapped_column(String(36))
    run_node_id: Mapped[str] = mapped_column(String(36))
    agent_id: Mapped[str] = mapped_column(String(100))
    agent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MCPInvocation(BaseModel):
    __tablename__ = "mcp_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("mcp_inv_"))
    run_id: Mapped[str] = mapped_column(String(36))
    subagent_invocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    mcp_id: Mapped[str] = mapped_column(String(100))
    mcp_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effect_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="requested")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    input_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
