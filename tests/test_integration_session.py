# tests/test_integration_session.py
"""Integration tests for the full session flow.

These tests exercise the full session flow WITHOUT calling the execution engine
(no LLM, no DB). They test the orchestrator logic, intent parsing, follow-up
generation, and request building end-to-end.
"""


def test_full_session_flow_sync():
    """Test session flow without execution engine."""
    from app.services.test_lab.session_orchestrator import SessionOrchestrator, parse_user_intent, build_follow_up_request
    from app.schemas.test_lab_session import TestSessionState

    orch = SessionOrchestrator()
    state = orch.create_session()
    assert state.current_status == "idle"

    state = orch.select_agent(state, "summary_agent", "Summary Agent", "1.0.0")
    assert state.target_agent_id == "summary_agent"

    intent = parse_user_intent("Test summary_agent on COMEX case", has_previous_run=False)
    assert intent["action"] == "initial_test"

    # Simulate completed run (skip execution)
    state.last_run_id = "trun_fake_123"
    state.last_verdict = "passed"
    state.last_score = 85.0
    state.last_objective = "Test COMEX summarization"
    state.recent_run_ids.append("trun_fake_123")

    # Test follow-up intent parsing
    intent = parse_user_intent("Run a stricter version", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "stricter"

    req = build_follow_up_request(state, "stricter", "COMEX summary task", [])
    assert req.agent_id == "summary_agent"
    assert req.source == "interactive"
    assert req.parent_run_id == "trun_fake_123"
    assert "stricter" in req.tags

    # Robustness
    intent = parse_user_intent("Propose an edge case", has_previous_run=True)
    assert intent["follow_up_type"] == "robustness"
    req = build_follow_up_request(state, "robustness", "COMEX summary task", [])
    assert "AMBIGUOUS" in req.input_prompt
    assert "robustness" in req.tags

    # Policy
    intent = parse_user_intent("Run a policy test", has_previous_run=True)
    assert intent["follow_up_type"] == "policy"
    req = build_follow_up_request(state, "policy", "COMEX summary task", [])
    assert "publish" in req.input_prompt.lower()
    assert "policy" in req.tags


def test_follow_up_options_generation():
    from app.services.test_lab.subagents import generate_follow_up_options

    # Passed test
    options = generate_follow_up_options("passed", 85.0, [], [])
    keys = [o.key for o in options]
    assert "rerun" in keys
    assert "stricter" in keys
    assert "robustness" in keys
    assert "policy" in keys

    # Failed test with diagnostics
    options = generate_follow_up_options(
        "failed", 35.0,
        [{"code": "expected_tool_not_used", "severity": "error"}],
        [{"assertion_type": "tool_called", "target": "search"}],
    )
    keys = [o.key for o in options]
    assert "targeted" in keys
    assert "tool_usage" in keys


def test_backward_compatibility():
    """Verify orchestrator.py still exports the expected names."""
    from app.services.test_lab.orchestrator import emit, update_run, run_test
    assert callable(emit)
    assert callable(update_run)
    assert callable(run_test)


def test_execution_engine_exports():
    from app.services.test_lab.execution_engine import (
        execute_test_run, execute_test_from_request,
        emit_event, update_run, run_subagent, PHASES
    )
    assert callable(execute_test_run)
    assert callable(execute_test_from_request)
    assert callable(emit_event)
    assert callable(update_run)
    assert callable(run_subagent)
    assert len(PHASES) == 5
