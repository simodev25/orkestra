"""Tests for TargetAgentResult dataclass and _build_execution_events helper.

Real agent execution (run_target_agent) is NOT tested here — it requires
a live database session, AgentScope, and an LLM provider.
"""

import pytest

from app.services.test_lab.target_agent_runner import (
    TargetAgentResult,
    _build_execution_events,
)


# ── TargetAgentResult dataclass ───────────────────────────────────────────────


def test_target_agent_result_dataclass():
    result = TargetAgentResult(
        status="completed",
        final_output="Summary.",
        duration_ms=1500,
        iteration_count=3,
        message_history=[{"role": "assistant", "content": "summary"}],
        tool_calls=[],
        error=None,
    )
    assert result.status == "completed"
    assert result.final_output == "Summary."
    assert result.duration_ms == 1500
    assert result.iteration_count == 3
    assert result.error is None
    assert len(result.message_history) == 1


def test_target_agent_result_failed():
    result = TargetAgentResult(
        status="failed",
        final_output="",
        duration_ms=500,
        iteration_count=0,
        message_history=[],
        tool_calls=[],
        error="Agent creation failed",
    )
    assert result.status == "failed"
    assert result.error is not None
    assert result.error == "Agent creation failed"
    assert result.final_output == ""
    assert result.iteration_count == 0


def test_target_agent_result_timeout():
    result = TargetAgentResult(
        status="timeout",
        final_output="",
        duration_ms=120_000,
        iteration_count=0,
        error="Timed out after 120s",
    )
    assert result.status == "timeout"
    assert result.error is not None
    assert result.duration_ms == 120_000


def test_target_agent_result_defaults():
    """Default fields should be empty lists and None error."""
    result = TargetAgentResult(
        status="completed",
        final_output="ok",
        duration_ms=100,
        iteration_count=1,
    )
    assert result.message_history == []
    assert result.tool_calls == []
    assert result.error is None


# ── _build_execution_events ────────────────────────────────────────────────────


def test_build_execution_events():
    msgs = [
        {"role": "assistant", "content": "Thinking..."},
        {"role": "tool", "name": "search", "content": "results"},
        {"role": "assistant", "content": "Final answer."},
    ]
    events = _build_execution_events(msgs)
    assert len(events) >= 2
    assert any(e["event_type"] == "tool_call_completed" for e in events)
    assert any(e["event_type"] == "iteration" for e in events)


def test_build_execution_events_only_assistant():
    msgs = [
        {"role": "assistant", "content": "Step 1"},
        {"role": "assistant", "content": "Step 2"},
    ]
    events = _build_execution_events(msgs)
    assert len(events) == 2
    assert all(e["event_type"] == "iteration" for e in events)
    assert all(e["phase"] == "runtime" for e in events)


def test_build_execution_events_only_tool():
    msgs = [
        {"role": "tool", "name": "calc", "content": "42"},
    ]
    events = _build_execution_events(msgs)
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_call_completed"
    assert events[0]["name"] == "calc"


def test_build_execution_events_ignores_user_and_system():
    msgs = [
        {"role": "user", "content": "Hello"},
        {"role": "system", "content": "You are an agent."},
        {"role": "assistant", "content": "I will help."},
    ]
    events = _build_execution_events(msgs)
    # Only the assistant message produces an event
    assert len(events) == 1
    assert events[0]["event_type"] == "iteration"


def test_build_execution_events_empty():
    events = _build_execution_events([])
    assert events == []


def test_build_execution_events_preserves_index():
    msgs = [
        {"role": "assistant", "content": "A"},
        {"role": "tool", "name": "t", "content": "B"},
    ]
    events = _build_execution_events(msgs)
    assert events[0]["index"] == 0
    assert events[1]["index"] == 1


def test_build_execution_events_tool_carries_name():
    msgs = [{"role": "tool", "name": "web_search", "content": "results here"}]
    events = _build_execution_events(msgs)
    assert events[0]["name"] == "web_search"
    assert events[0]["content"] == "results here"
