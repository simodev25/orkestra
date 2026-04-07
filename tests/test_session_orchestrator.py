"""Tests for the Interactive Test Lab Session Orchestrator."""

from __future__ import annotations

import pytest

from app.schemas.test_lab_session import TestSessionState
from app.services.test_lab.session_orchestrator import (
    SessionOrchestrator,
    build_follow_up_request,
    parse_user_intent,
)


# ---------------------------------------------------------------------------
# SessionOrchestrator.create_session
# ---------------------------------------------------------------------------


def test_create_session():
    orch = SessionOrchestrator()
    state = orch.create_session()
    assert state.session_id.startswith("sess_")
    assert state.current_status == "idle"


def test_create_session_returns_test_session_state():
    orch = SessionOrchestrator()
    state = orch.create_session()
    assert isinstance(state, TestSessionState)


def test_create_session_has_empty_conversation():
    orch = SessionOrchestrator()
    state = orch.create_session()
    assert state.conversation == []


def test_create_session_unique_ids():
    orch = SessionOrchestrator()
    s1 = orch.create_session()
    s2 = orch.create_session()
    assert s1.session_id != s2.session_id


# ---------------------------------------------------------------------------
# SessionOrchestrator.select_agent
# ---------------------------------------------------------------------------


def test_select_agent():
    orch = SessionOrchestrator()
    state = orch.create_session()
    state = orch.select_agent(state, "summary_agent", "Summary Agent", "1.0.0")
    assert state.target_agent_id == "summary_agent"
    assert state.target_agent_label == "Summary Agent"


def test_select_agent_sets_version():
    orch = SessionOrchestrator()
    state = orch.create_session()
    state = orch.select_agent(state, "risk_agent", "Risk Agent", "2.1.0")
    assert state.target_agent_version == "2.1.0"


def test_select_agent_adds_system_message():
    orch = SessionOrchestrator()
    state = orch.create_session()
    state = orch.select_agent(state, "my_agent", "My Agent")
    assert len(state.conversation) == 1
    assert state.conversation[0].role == "system"
    assert "my_agent" in state.conversation[0].content


def test_select_agent_no_label_uses_id():
    orch = SessionOrchestrator()
    state = orch.create_session()
    state = orch.select_agent(state, "anon_agent")
    assert state.target_agent_id == "anon_agent"
    assert state.target_agent_label is None


# ---------------------------------------------------------------------------
# parse_user_intent — initial_test
# ---------------------------------------------------------------------------


def test_parse_user_intent_initial_test():
    intent = parse_user_intent(
        "Test summary_agent on a COMEX cyber-risk case", has_previous_run=False
    )
    assert intent["action"] == "initial_test"


def test_parse_user_intent_initial_test_no_previous_run():
    intent = parse_user_intent("Run a policy test on my agent", has_previous_run=False)
    # Without a previous run, policy keywords fall through to initial_test
    assert intent["action"] == "initial_test"


def test_parse_user_intent_agent_hint_extracted():
    intent = parse_user_intent(
        "Test summary_agent on something", has_previous_run=False
    )
    assert intent["agent_hint"] == "summary_agent"


# ---------------------------------------------------------------------------
# parse_user_intent — follow_up types
# ---------------------------------------------------------------------------


def test_parse_user_intent_stricter():
    intent = parse_user_intent("Now run a stricter version", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "stricter"


def test_parse_user_intent_stricter_tighter():
    intent = parse_user_intent("Make it tighter this time", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "stricter"


def test_parse_user_intent_stricter_harder():
    intent = parse_user_intent("Run a harder test", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "stricter"


def test_parse_user_intent_edge_case():
    intent = parse_user_intent(
        "Propose an edge case and execute it", has_previous_run=True
    )
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "robustness"


def test_parse_user_intent_robustness():
    intent = parse_user_intent("Run a robustness test", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "robustness"


def test_parse_user_intent_adversarial():
    intent = parse_user_intent("Try an adversarial input", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "robustness"


def test_parse_user_intent_ambiguous():
    intent = parse_user_intent("Use an ambiguous input", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "robustness"


def test_parse_user_intent_policy():
    intent = parse_user_intent("Run a policy-oriented follow-up", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "policy"


def test_parse_user_intent_governance():
    intent = parse_user_intent("Check governance compliance", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "policy"


def test_parse_user_intent_compliance():
    intent = parse_user_intent("Test for compliance issues", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "policy"


def test_parse_user_intent_rerun():
    intent = parse_user_intent("Replay the previous test", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "rerun"


def test_parse_user_intent_again():
    intent = parse_user_intent("Run it again", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "rerun"


def test_parse_user_intent_rerun_keyword():
    intent = parse_user_intent("rerun the same test", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "rerun"


def test_parse_user_intent_compare():
    intent = parse_user_intent("Compare the two runs", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "compare"


def test_parse_user_intent_targeted():
    intent = parse_user_intent("Focus on the failing assertions", has_previous_run=True)
    assert intent["action"] == "follow_up"
    assert intent["follow_up_type"] == "targeted"


# ---------------------------------------------------------------------------
# parse_user_intent — select_agent
# ---------------------------------------------------------------------------


def test_parse_user_intent_select_agent():
    intent = parse_user_intent("use summary_agent", has_previous_run=False)
    assert intent["action"] == "select_agent"
    assert intent["agent_hint"] == "summary_agent"


def test_parse_user_intent_switch_to():
    intent = parse_user_intent("switch to risk_agent", has_previous_run=False)
    assert intent["action"] == "select_agent"
    assert intent["agent_hint"] == "risk_agent"


# ---------------------------------------------------------------------------
# parse_user_intent — help
# ---------------------------------------------------------------------------


def test_parse_user_intent_help():
    intent = parse_user_intent("help", has_previous_run=False)
    assert intent["action"] == "help"


# ---------------------------------------------------------------------------
# build_follow_up_request — stricter
# ---------------------------------------------------------------------------


def test_build_follow_up_request_stricter():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test summarization",
        last_score=85.0,
        last_verdict="passed",
        last_run_id="trun_123",
    )
    request = build_follow_up_request(state, "stricter", "Summarize this report", [])
    assert request.agent_id == "my_agent"
    assert request.source == "interactive"
    assert request.parent_run_id == "trun_123"
    assert "stricter" in request.tags


def test_build_follow_up_request_stricter_halves_timeout():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_123",
    )
    request = build_follow_up_request(state, "stricter", "Some input", [])
    assert request.timeout_seconds <= 30  # half of 60
    assert request.max_iterations <= 4  # half of 8


def test_build_follow_up_request_stricter_adds_assertions_when_empty():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_123",
    )
    request = build_follow_up_request(state, "stricter", "Some input", [])
    assert len(request.assertions) > 0


# ---------------------------------------------------------------------------
# build_follow_up_request — robustness
# ---------------------------------------------------------------------------


def test_build_follow_up_request_robustness():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_123",
    )
    request = build_follow_up_request(state, "robustness", "Original input", [])
    assert "AMBIGUOUS" in request.input_prompt
    assert "robustness" in request.tags


def test_build_follow_up_request_robustness_preserves_original():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_123",
    )
    request = build_follow_up_request(state, "robustness", "Original input", [])
    assert "Original input" in request.input_prompt


# ---------------------------------------------------------------------------
# build_follow_up_request — policy
# ---------------------------------------------------------------------------


def test_build_follow_up_request_policy():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_123",
    )
    request = build_follow_up_request(state, "policy", "Original input", [])
    assert "publish" in request.input_prompt.lower()
    assert "policy" in request.tags


def test_build_follow_up_request_policy_has_session_id():
    state = TestSessionState(
        session_id="sess_abc",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_456",
    )
    request = build_follow_up_request(state, "policy", "input", [])
    assert request.session_id == "sess_abc"
    assert request.parent_run_id == "trun_456"


# ---------------------------------------------------------------------------
# build_follow_up_request — rerun
# ---------------------------------------------------------------------------


def test_build_follow_up_request_rerun_same_input():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="my_agent",
        last_objective="Test",
        last_run_id="trun_123",
    )
    original = "Summarize the risk report"
    request = build_follow_up_request(state, "rerun", original, [])
    assert request.input_prompt == original
    assert "rerun" in request.tags


# ---------------------------------------------------------------------------
# build_follow_up_request — common fields
# ---------------------------------------------------------------------------


def test_build_follow_up_request_source_is_interactive():
    state = TestSessionState(
        session_id="sess_x",
        target_agent_id="agent_y",
        last_objective="Test",
        last_run_id="trun_789",
    )
    for ftype in ("stricter", "robustness", "policy", "rerun", "compare", "targeted"):
        req = build_follow_up_request(state, ftype, "input", [])
        assert req.source == "interactive", f"source != 'interactive' for type={ftype}"


def test_build_follow_up_request_preserves_assertions():
    state = TestSessionState(
        session_id="sess_test",
        target_agent_id="agent_a",
        last_objective="Test",
        last_run_id="trun_001",
    )
    orig_assertions = [{"assertion_type": "output_contains", "target": "summary"}]
    request = build_follow_up_request(state, "rerun", "input", orig_assertions)
    assert orig_assertions[0] in request.assertions
