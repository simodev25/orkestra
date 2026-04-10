"""Interactive Test Lab Session — API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import OrkBaseSchema


class SessionMessage(OrkBaseSchema):
    role: Literal["user", "orchestrator", "system"]
    content: str
    metadata: dict | None = None


class FollowUpOption(OrkBaseSchema):
    key: str
    label: str
    description: str


class TestSessionState(OrkBaseSchema):
    session_id: str
    target_agent_id: str | None = None
    target_agent_label: str | None = None
    target_agent_version: str | None = None
    current_status: Literal["idle", "running", "awaiting_user", "completed"] = "idle"
    last_objective: str | None = None
    last_scenario_id: str | None = None
    last_run_id: str | None = None
    last_verdict: str | None = None
    last_score: float | None = None
    recent_run_ids: list[str] = Field(default_factory=list)
    available_followups: list[str] = Field(default_factory=list)
    conversation: list[SessionMessage] = Field(default_factory=list)


class TestExecutionRequest(OrkBaseSchema):
    agent_id: str
    objective: str
    input_prompt: str
    input_payload: dict | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)
    timeout_seconds: int = 60
    max_iterations: int = 8
    retry_count: int = 0
    assertions: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: Literal["batch", "interactive"] = "interactive"
    parent_run_id: str | None = None
    session_id: str | None = None


class TestExecutionResult(OrkBaseSchema):
    run_id: str
    scenario_id: str | None = None
    verdict: str
    score: float
    duration_ms: int | None = None
    summary: str | None = None
    assertion_count: int = 0
    assertion_passed: int = 0
    diagnostic_count: int = 0
    error: str | None = None
    followup_suggestions: list[FollowUpOption] = Field(default_factory=list)
