"""Tests for all state machines."""

import pytest
from app.state_machines.request_sm import RequestStateMachine
from app.state_machines.case_sm import CaseStateMachine
from app.state_machines.run_sm import RunStateMachine
from app.state_machines.plan_sm import PlanStateMachine
from app.state_machines.approval_sm import ApprovalStateMachine
from app.state_machines.agent_lifecycle_sm import AgentLifecycleStateMachine
from app.state_machines.mcp_lifecycle_sm import MCPLifecycleStateMachine


class TestRequestStateMachine:
    def test_happy_path(self):
        sm = RequestStateMachine()
        assert sm.state == "draft"
        assert sm.transition("submitted")
        assert sm.transition("accepted")
        assert sm.transition("converted_to_case")
        assert sm.is_terminal

    def test_reject(self):
        sm = RequestStateMachine()
        sm.transition("submitted")
        assert sm.transition("rejected")
        assert sm.is_terminal

    def test_invalid_transition(self):
        sm = RequestStateMachine()
        assert not sm.transition("completed")
        assert sm.state == "draft"

    def test_cancel_from_draft(self):
        sm = RequestStateMachine()
        assert sm.transition("cancelled")
        assert sm.is_terminal

    def test_history(self):
        sm = RequestStateMachine()
        sm.transition("submitted", reason="user clicked submit")
        assert len(sm.history) == 1
        assert sm.history[0].from_state == "draft"
        assert sm.history[0].to_state == "submitted"
        assert sm.history[0].reason == "user clicked submit"


class TestCaseStateMachine:
    def test_happy_path(self):
        sm = CaseStateMachine()
        assert sm.transition("ready_for_planning")
        assert sm.transition("planning")
        assert sm.transition("running")
        assert sm.transition("completed")
        assert sm.transition("archived")
        assert sm.is_terminal

    def test_blocked_recovery(self):
        sm = CaseStateMachine()
        sm.transition("ready_for_planning")
        sm.transition("planning")
        assert sm.transition("blocked")
        assert sm.transition("planning")


class TestRunStateMachine:
    def test_happy_path(self):
        sm = RunStateMachine()
        assert sm.transition("planned")
        assert sm.transition("running")
        assert sm.transition("completed")
        assert sm.is_terminal

    def test_waiting_review(self):
        sm = RunStateMachine()
        sm.transition("planned")
        sm.transition("running")
        assert sm.transition("waiting_review")
        assert sm.transition("running")

    def test_hold_resume(self):
        sm = RunStateMachine()
        sm.transition("planned")
        sm.transition("running")
        assert sm.transition("hold")
        assert sm.transition("running")

    def test_terminal_states(self):
        for terminal in ["completed", "failed", "cancelled"]:
            sm = RunStateMachine()
            sm.transition("planned")
            if terminal == "cancelled":
                assert sm.transition("cancelled")
            else:
                sm.transition("running")
                assert sm.transition(terminal)
            assert sm.is_terminal


class TestPlanStateMachine:
    def test_validated_then_executing(self):
        sm = PlanStateMachine()
        assert sm.transition("validated")
        assert sm.transition("executing")
        assert sm.transition("completed")

    def test_adjusted_then_executing(self):
        sm = PlanStateMachine()
        assert sm.transition("adjusted_by_control")
        assert sm.transition("executing")

    def test_rejected_is_terminal(self):
        sm = PlanStateMachine()
        assert sm.transition("rejected")
        assert sm.is_terminal


class TestApprovalStateMachine:
    def test_approve_flow(self):
        sm = ApprovalStateMachine()
        assert sm.transition("assigned")
        assert sm.transition("pending")
        assert sm.transition("approved")
        assert sm.is_terminal

    def test_reject_flow(self):
        sm = ApprovalStateMachine()
        sm.transition("assigned")
        sm.transition("pending")
        assert sm.transition("rejected")
        assert sm.is_terminal

    def test_refine_required(self):
        sm = ApprovalStateMachine()
        sm.transition("assigned")
        sm.transition("pending")
        assert sm.transition("refine_required")
        assert sm.is_terminal


class TestAgentLifecycleStateMachine:
    def test_happy_path(self):
        sm = AgentLifecycleStateMachine()
        assert sm.transition("tested")
        assert sm.transition("registered")
        assert sm.transition("active")
        assert not sm.is_terminal

    def test_deprecate_archive(self):
        sm = AgentLifecycleStateMachine()
        sm.transition("tested")
        sm.transition("registered")
        sm.transition("active")
        assert sm.transition("deprecated")
        assert sm.transition("archived")
        assert sm.is_terminal

    def test_disable_reactivate(self):
        sm = AgentLifecycleStateMachine()
        sm.transition("tested")
        sm.transition("registered")
        sm.transition("active")
        assert sm.transition("disabled")
        assert sm.transition("active")


class TestMCPLifecycleStateMachine:
    def test_degraded_recovery(self):
        sm = MCPLifecycleStateMachine()
        sm.transition("tested")
        sm.transition("registered")
        sm.transition("active")
        assert sm.transition("degraded")
        assert sm.transition("active")

    def test_disabled_to_archived(self):
        sm = MCPLifecycleStateMachine()
        sm.transition("tested")
        sm.transition("registered")
        sm.transition("active")
        sm.transition("disabled")
        assert sm.transition("archived")
        assert sm.is_terminal
