"""Tests for subagent executor and MCP executor."""

import pytest
from app.models.registry import AgentDefinition, MCPDefinition
from app.models.run import Run, RunNode
from app.models.enums import RunNodeStatus, AgentStatus, MCPStatus
from app.services.subagent_executor import execute_subagent
from app.services.mcp_executor import invoke_mcp


async def _setup_agent(db_session, agent_id="test_agent"):
    agent = AgentDefinition(
        id=agent_id, name="Test Agent", family="analysis",
        purpose="Test agent", version="1.0.0", status=AgentStatus.ACTIVE,
        allowed_mcps=["doc_parser"],
    )
    db_session.add(agent)
    await db_session.flush()
    return agent


async def _setup_mcp(db_session, mcp_id="doc_parser", allowed_agents=None):
    mcp = MCPDefinition(
        id=mcp_id, name="Doc Parser", purpose="Parse docs",
        effect_type="read", version="1.0.0", status=MCPStatus.ACTIVE,
        allowed_agents=allowed_agents or ["test_agent"],
    )
    db_session.add(mcp)
    await db_session.flush()
    return mcp


async def _setup_run_with_node(db_session, agent_id="test_agent"):
    run = Run(case_id="case_1", plan_id="plan_1", status="running")
    db_session.add(run)
    await db_session.flush()
    node = RunNode(
        run_id=run.id, node_type="subagent", node_ref=agent_id,
        status=RunNodeStatus.READY, order_index=0,
    )
    db_session.add(node)
    await db_session.flush()
    return run, node


class TestSubagentExecutor:
    async def test_execute_subagent_success(self, db_session):
        await _setup_agent(db_session)
        run, node = await _setup_run_with_node(db_session)
        await db_session.commit()

        invocation = await execute_subagent(db_session, run.id, node)
        await db_session.commit()

        assert invocation.status == "completed"
        assert invocation.agent_id == "test_agent"
        assert invocation.confidence_score == 0.85
        assert invocation.cost > 0
        assert node.status == RunNodeStatus.RUNNING

    async def test_execute_subagent_unknown_agent(self, db_session):
        run, node = await _setup_run_with_node(db_session, agent_id="nonexistent")
        await db_session.commit()

        with pytest.raises(ValueError, match="not found"):
            await execute_subagent(db_session, run.id, node)


class TestMCPExecutor:
    async def test_invoke_mcp_success(self, db_session):
        await _setup_agent(db_session)
        await _setup_mcp(db_session)
        run, _ = await _setup_run_with_node(db_session)
        await db_session.commit()

        inv = await invoke_mcp(db_session, run.id, "doc_parser", "test_agent")
        await db_session.commit()

        assert inv.status == "completed"
        assert inv.mcp_id == "doc_parser"
        assert inv.latency_ms == 120
        assert inv.cost > 0

    async def test_invoke_mcp_denied_by_allowlist(self, db_session):
        agent = AgentDefinition(
            id="restricted_agent", name="Restricted", family="test",
            purpose="Test restricted", version="1.0.0", status=AgentStatus.ACTIVE,
            allowed_mcps=["other_mcp"],  # doc_parser NOT in allowlist
        )
        db_session.add(agent)
        await _setup_mcp(db_session)
        run, _ = await _setup_run_with_node(db_session, agent_id="restricted_agent")
        await db_session.commit()

        inv = await invoke_mcp(db_session, run.id, "doc_parser", "restricted_agent")
        await db_session.commit()

        assert inv.status == "denied"

    async def test_invoke_mcp_not_found(self, db_session):
        await _setup_agent(db_session)
        run, _ = await _setup_run_with_node(db_session)
        await db_session.commit()

        with pytest.raises(ValueError, match="not found"):
            await invoke_mcp(db_session, run.id, "nonexistent_mcp", "test_agent")

    async def test_invoke_disabled_mcp(self, db_session):
        await _setup_agent(db_session)
        mcp = MCPDefinition(
            id="disabled_mcp", name="Disabled", purpose="Test disabled",
            effect_type="read", version="1.0.0", status=MCPStatus.DISABLED,
        )
        db_session.add(mcp)
        run, _ = await _setup_run_with_node(db_session)
        await db_session.commit()

        with pytest.raises(ValueError, match="not available"):
            await invoke_mcp(db_session, run.id, "disabled_mcp", "test_agent")
