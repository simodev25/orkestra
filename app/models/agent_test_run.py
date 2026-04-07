"""Agent Test Run — persists test lab execution results."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import BaseModel


class AgentTestRun(BaseModel):
    __tablename__ = "agent_test_runs"

    agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    agent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed, error
    verdict: Mapped[str] = mapped_column(String(10), nullable=False)  # pass, fail, error
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider: Mapped[str] = mapped_column(String(50), nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=True)
    raw_output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    task: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    behavioral_checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # system_prompt, tools, skills, etc.
