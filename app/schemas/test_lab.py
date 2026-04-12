"""Agentic Test Lab — API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import OrkBaseSchema


# ── Assertion definition (inside scenario) ─────────────────────────────

class AssertionDef(OrkBaseSchema):
    type: str = Field(..., description="One of: tool_called, tool_not_called, output_field_exists, output_schema_matches, max_duration_ms, max_iterations, final_status_is, no_tool_failures, output_contains")
    target: Optional[str] = None
    expected: Optional[str] = None
    critical: bool = False


# ── Scenario ───────────────────────────────────────────────────────────

class ScenarioCreate(OrkBaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    agent_id: str = Field(..., min_length=1, max_length=100)
    input_prompt: str = Field(..., min_length=1)
    input_payload: Optional[dict] = None
    allowed_tools: Optional[list[str]] = None
    expected_tools: Optional[list[str]] = None
    timeout_seconds: int = Field(default=120, ge=5, le=600)
    max_iterations: int = Field(default=5, ge=1, le=20)
    retry_count: int = Field(default=0, ge=0, le=5)
    assertions: list[AssertionDef] = Field(default_factory=list)
    tags: Optional[list[str]] = None
    enabled: bool = True


class ScenarioUpdate(OrkBaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    input_prompt: Optional[str] = Field(None, min_length=1)
    input_payload: Optional[dict] = None
    allowed_tools: Optional[list[str]] = None
    expected_tools: Optional[list[str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=5, le=600)
    max_iterations: Optional[int] = Field(None, ge=1, le=20)
    retry_count: Optional[int] = Field(None, ge=0, le=5)
    assertions: Optional[list[AssertionDef]] = None
    tags: Optional[list[str]] = None
    enabled: Optional[bool] = None


class ScenarioOut(OrkBaseSchema):
    id: str
    name: str
    description: Optional[str]
    agent_id: str
    input_prompt: str
    input_payload: Optional[dict]
    allowed_tools: Optional[list[str]]
    expected_tools: Optional[list[str]]
    timeout_seconds: int
    max_iterations: int
    retry_count: int
    assertions: list[AssertionDef]
    tags: Optional[list[str]]
    enabled: bool
    created_at: datetime
    updated_at: datetime


# ── Run ────────────────────────────────────────────────────────────────

class RunOut(OrkBaseSchema):
    id: str
    scenario_id: str
    agent_id: str
    agent_version: str
    status: str
    verdict: Optional[str]
    score: Optional[float]
    duration_ms: Optional[int]
    final_output: Optional[str]
    summary: Optional[str]
    error_message: Optional[str]
    execution_metadata: Optional[dict]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime


# ── Event ──────────────────────────────────────────────────────────────

class EventOut(OrkBaseSchema):
    id: str
    run_id: str
    event_type: str
    phase: Optional[str]
    message: Optional[str]
    details: Optional[dict]
    timestamp: datetime
    duration_ms: Optional[int]


# ── Assertion result ───────────────────────────────────────────────────

class AssertionResultOut(OrkBaseSchema):
    id: str
    run_id: str
    assertion_type: str
    target: Optional[str]
    expected: Optional[str]
    actual: Optional[str]
    passed: bool
    critical: bool
    message: str
    details: Optional[dict]


# ── Diagnostic ─────────────────────────────────────────────────────────

class DiagnosticOut(OrkBaseSchema):
    id: str
    run_id: str
    code: str
    severity: str
    message: str
    probable_causes: Optional[list[str]]
    recommendation: Optional[str]
    evidence: Optional[dict]


# ── Agent test summary ─────────────────────────────────────────────────

class AgentTestSummary(OrkBaseSchema):
    agent_id: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    warning_runs: int
    pass_rate: float
    average_score: float
    last_run_at: Optional[datetime]
    last_verdict: Optional[str]
    tool_failure_rate: float
    timeout_rate: float
    average_duration_ms: float
    eligible_for_tested: bool


# ── Run report (composite) ─────────────────────────────────────────────

class RunReport(OrkBaseSchema):
    run: RunOut
    events: list[EventOut]
    assertions: list[AssertionResultOut]
    diagnostics: list[DiagnosticOut]
    scenario: ScenarioOut


# ── Test Lab Configuration ────────────────────────────────────────────

class TestLabConfig(OrkBaseSchema):
    """Validation schema for Test Lab configuration."""
    default_agent_id: Optional[str] = None
    default_timeout_seconds: int = Field(default=120, ge=10, le=600)
    default_max_iterations: int = Field(default=5, ge=1, le=20)
    default_model_provider: str = Field(default="ollama", pattern="^(ollama|openai)$")
    default_model_name: str = Field(default="mistral")
    scoring_pass_threshold: int = Field(default=80, ge=0, le=100)
    scoring_warning_threshold: int = Field(default=50, ge=0, le=100)
