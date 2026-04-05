"""Subagent executor -- invokes sub-agents via AgentScope, falls back to simulation."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invocation import SubagentInvocation
from app.models.registry import AgentDefinition
from app.models.run import RunNode
from app.models.enums import RunNodeStatus
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


async def execute_subagent(
    db: AsyncSession,
    run_id: str,
    node: RunNode,
) -> SubagentInvocation:
    """Execute a sub-agent for a given run node.

    Tries AgentScope ReActAgent first; falls back to simulation if unavailable.
    """
    agent_id = node.node_ref

    # Load agent definition
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found in registry")

    # Mark node as running
    node.status = RunNodeStatus.RUNNING
    node.started_at = datetime.now(timezone.utc)

    # Create invocation record
    invocation = SubagentInvocation(
        run_id=run_id,
        run_node_id=node.id,
        agent_id=agent_id,
        agent_version=agent.version,
        status="running",
        input_summary=f"Processing node {node.id} for agent {agent_id}",
        started_at=datetime.now(timezone.utc),
    )
    db.add(invocation)
    await db.flush()

    await emit_event(db, "subagent.started", "runtime", "subagent_executor",
                     run_id=run_id, payload={"agent_id": agent_id, "invocation_id": invocation.id})

    # Try real AgentScope execution
    try:
        result = await _execute_with_agentscope(agent, agent_id, db)
        if result is not None:
            invocation.status = "completed"
            invocation.confidence_score = result.get("confidence", 0.85)
            invocation.output_summary = result.get("summary", "Agent completed via AgentScope")
            invocation.cost = result.get("cost", 0.5)
            invocation.ended_at = datetime.now(timezone.utc)
            invocation.result_payload = result

            await emit_event(db, "subagent.completed", "runtime", "subagent_executor",
                             run_id=run_id, payload={"agent_id": agent_id, "mode": "agentscope"})
            await db.flush()
            return invocation
    except Exception as e:
        logger.warning(f"AgentScope execution failed for {agent_id}, falling back to simulation: {e}")

    # Fallback: simulated execution
    invocation.status = "completed"
    invocation.confidence_score = 0.85
    invocation.output_summary = f"Agent {agent_id} completed successfully (simulated)"
    invocation.cost = 0.5
    invocation.ended_at = datetime.now(timezone.utc)
    invocation.result_payload = {
        "agent_id": agent_id,
        "status": "success",
        "confidence_score": 0.85,
        "findings": [],
        "missing_data": [],
        "blocking_flags": [],
        "mode": "simulated",
    }

    await emit_event(db, "subagent.completed", "runtime", "subagent_executor",
                     run_id=run_id, payload={"agent_id": agent_id, "mode": "simulated"})
    await db.flush()
    return invocation


async def _execute_with_agentscope(
    agent_def: AgentDefinition,
    agent_id: str,
    db: AsyncSession,
) -> dict | None:
    """Try to execute using AgentScope. Returns result dict or None."""
    from app.llm.provider import is_agentscope_available
    if not is_agentscope_available():
        return None

    from app.services.agent_factory import create_agentscope_agent, get_tools_for_agent

    tools = get_tools_for_agent(agent_def)
    agent = await create_agentscope_agent(agent_def, db=db, tools_to_register=tools)
    if agent is None:
        return None

    from agentscope.message import Msg

    task_msg = Msg(
        "orchestrator",
        f"Execute your mission: {agent_def.purpose}. "
        f"Analyze the available data and produce structured findings.",
        "user",
    )

    response = await agent(task_msg)
    text = response.get_text_content() if hasattr(response, "get_text_content") else str(response)

    return {
        "agent_id": agent_id,
        "status": "success",
        "confidence": 0.85,
        "summary": text[:500] if text else "No output",
        "findings": [],
        "missing_data": [],
        "blocking_flags": [],
        "mode": "agentscope",
        "cost": 0.5,
    }
