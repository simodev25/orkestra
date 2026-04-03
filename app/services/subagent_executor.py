"""Subagent executor — invokes sub-agents, validates contracts, records results."""

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

    In Phase 2, this is a simulated execution that records the invocation.
    Real LLM integration comes in a later phase.
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

    # Simulated execution — in production this would call AgentScope
    try:
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
        }

        await emit_event(db, "subagent.completed", "runtime", "subagent_executor",
                         run_id=run_id, payload={"agent_id": agent_id, "invocation_id": invocation.id})

    except Exception as e:
        invocation.status = "failed"
        invocation.error_code = "EXECUTION_ERROR"
        invocation.error_message = str(e)
        invocation.ended_at = datetime.now(timezone.utc)

        await emit_event(db, "subagent.failed", "runtime", "subagent_executor",
                         run_id=run_id, payload={"agent_id": agent_id, "error": str(e)})

    await db.flush()
    return invocation
