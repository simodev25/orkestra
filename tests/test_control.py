"""Tests for control service and API."""

import pytest
from app.models.settings import PolicyProfile, BudgetProfile
from app.models.run import Run
from app.models.registry import AgentDefinition, MCPDefinition
from app.models.enums import AgentStatus, MCPStatus
from app.services.control_service import (
    evaluate_plan, check_agent_authorization, check_mcp_authorization,
    get_decisions_for_run,
)


async def _setup_budget(db_session, soft=5.0, hard=10.0):
    budget = BudgetProfile(name="default", soft_limit=soft, hard_limit=hard, is_default=True)
    db_session.add(budget)
    await db_session.flush()
    return budget


async def _setup_policy(db_session, rules=None):
    policy = PolicyProfile(name="default", rules=rules or {}, is_default=True)
    db_session.add(policy)
    await db_session.flush()
    return policy


async def _setup_run(db_session):
    run = Run(case_id="case_1", plan_id="plan_1", status="planned")
    db_session.add(run)
    await db_session.flush()
    return run


class TestPlanEvaluation:
    async def test_plan_allowed_no_violations(self, db_session):
        run = await _setup_run(db_session)
        await db_session.commit()

        decisions = await evaluate_plan(db_session, run.id, [], [], 1.0)
        await db_session.commit()
        assert len(decisions) == 1
        assert decisions[0].decision_type == "allow"

    async def test_plan_denied_budget_hard_limit(self, db_session):
        await _setup_budget(db_session, hard=5.0)
        run = await _setup_run(db_session)
        await db_session.commit()

        decisions = await evaluate_plan(db_session, run.id, [], [], 15.0)
        await db_session.commit()
        assert any(d.decision_type == "deny" for d in decisions)
        assert any("hard limit" in d.reason for d in decisions)

    async def test_plan_hold_budget_soft_limit(self, db_session):
        await _setup_budget(db_session, soft=3.0, hard=20.0)
        run = await _setup_run(db_session)
        await db_session.commit()

        decisions = await evaluate_plan(db_session, run.id, [], [], 5.0)
        await db_session.commit()
        assert any(d.decision_type == "hold" for d in decisions)

    async def test_high_criticality_requires_review(self, db_session):
        await _setup_policy(db_session, rules={"high_criticality_requires_review": True})
        run = await _setup_run(db_session)
        await db_session.commit()

        decisions = await evaluate_plan(db_session, run.id, [], [], 1.0, criticality="high")
        await db_session.commit()
        assert any(d.decision_type == "review_required" for d in decisions)


class TestAgentAuthorization:
    async def test_active_agent_allowed(self, db_session):
        agent = AgentDefinition(id="good_agent", name="Good", family="test",
                                purpose="Test", status=AgentStatus.ACTIVE)
        db_session.add(agent)
        run = await _setup_run(db_session)
        await db_session.commit()

        d = await check_agent_authorization(db_session, run.id, "good_agent")
        await db_session.commit()
        assert d.decision_type == "allow"

    async def test_inactive_agent_denied(self, db_session):
        agent = AgentDefinition(id="draft_agent", name="Draft", family="test",
                                purpose="Test", status=AgentStatus.DRAFT)
        db_session.add(agent)
        run = await _setup_run(db_session)
        await db_session.commit()

        d = await check_agent_authorization(db_session, run.id, "draft_agent")
        await db_session.commit()
        assert d.decision_type == "deny"

    async def test_unknown_agent_denied(self, db_session):
        run = await _setup_run(db_session)
        await db_session.commit()

        d = await check_agent_authorization(db_session, run.id, "nonexistent")
        await db_session.commit()
        assert d.decision_type == "deny"


class TestMCPAuthorization:
    async def test_mcp_allowed(self, db_session):
        agent = AgentDefinition(id="agent_1", name="A1", family="test",
                                purpose="Test", status=AgentStatus.ACTIVE,
                                allowed_mcps=["doc_parser"])
        mcp = MCPDefinition(id="doc_parser", name="Parser", purpose="Parse",
                            effect_type="read", status=MCPStatus.ACTIVE)
        db_session.add(agent)
        db_session.add(mcp)
        run = await _setup_run(db_session)
        await db_session.commit()

        d = await check_mcp_authorization(db_session, run.id, "doc_parser", "agent_1")
        await db_session.commit()
        assert d.decision_type == "allow"

    async def test_mcp_denied_not_in_allowlist(self, db_session):
        agent = AgentDefinition(id="agent_1", name="A1", family="test",
                                purpose="Test", status=AgentStatus.ACTIVE,
                                allowed_mcps=["other_mcp"])
        mcp = MCPDefinition(id="doc_parser", name="Parser", purpose="Parse",
                            effect_type="read", status=MCPStatus.ACTIVE)
        db_session.add(agent)
        db_session.add(mcp)
        run = await _setup_run(db_session)
        await db_session.commit()

        d = await check_mcp_authorization(db_session, run.id, "doc_parser", "agent_1")
        await db_session.commit()
        assert d.decision_type == "deny"

    async def test_sensitive_mcp_requires_review(self, db_session):
        agent = AgentDefinition(id="agent_1", name="A1", family="test",
                                purpose="Test", status=AgentStatus.ACTIVE,
                                allowed_mcps=["ext_writer"])
        mcp = MCPDefinition(id="ext_writer", name="Writer", purpose="Write",
                            effect_type="write", status=MCPStatus.ACTIVE,
                            approval_required=True)
        db_session.add(agent)
        db_session.add(mcp)
        run = await _setup_run(db_session)
        await db_session.commit()

        d = await check_mcp_authorization(db_session, run.id, "ext_writer", "agent_1")
        await db_session.commit()
        assert d.decision_type == "review_required"


class TestControlAPI:
    async def test_list_control_decisions(self, client):
        resp = await client.get("/api/control-decisions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
