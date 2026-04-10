"""Tests for interactive Test Lab session schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.test_lab_session import (
    FollowUpOption,
    SessionMessage,
    TestExecutionRequest,
    TestExecutionResult,
    TestSessionState,
)


def test_test_session_state_defaults():
    state = TestSessionState(session_id="sess_abc123")
    assert state.session_id == "sess_abc123"
    assert state.target_agent_id is None
    assert state.current_status == "idle"
    assert state.recent_run_ids == []
    assert state.available_followups == []


def test_test_execution_request_required_fields():
    req = TestExecutionRequest(
        agent_id="my_agent",
        objective="Test summarization quality",
        input_prompt="Summarize this document.",
    )
    assert req.agent_id == "my_agent"
    assert req.source == "interactive"
    assert req.timeout_seconds == 60
    assert req.max_iterations == 8


def test_test_execution_request_validation():
    # Missing agent_id should fail
    with pytest.raises(ValidationError):
        TestExecutionRequest(objective="missing agent_id", input_prompt="test")


def test_test_execution_result():
    result = TestExecutionResult(
        run_id="trun_abc",
        scenario_id="scn_xyz",
        verdict="passed",
        score=85.0,
        duration_ms=1200,
        summary="Passed.",
        assertion_count=3,
        assertion_passed=3,
        diagnostic_count=0,
    )
    assert result.verdict == "passed"


def test_session_message():
    msg = SessionMessage(role="user", content="Test my agent")
    assert msg.role == "user"


def test_follow_up_option():
    opt = FollowUpOption(
        key="stricter",
        label="Run stricter version",
        description="Increase thresholds",
    )
    assert opt.key == "stricter"
