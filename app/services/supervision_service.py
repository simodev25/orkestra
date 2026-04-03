"""Supervision service — live state aggregation, run metrics."""

import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import Run, RunNode
from app.models.invocation import SubagentInvocation, MCPInvocation
from app.models.control import ControlDecision
from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)


async def get_run_live_state(db: AsyncSession, run_id: str) -> dict:
    """Aggregate live state for a run: status, nodes, costs, invocations."""
    run = await db.get(Run, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    # Get nodes
    stmt = select(RunNode).where(RunNode.run_id == run_id).order_by(RunNode.order_index)
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    # Get agent invocations
    stmt = select(SubagentInvocation).where(SubagentInvocation.run_id == run_id)
    result = await db.execute(stmt)
    agent_invocations = list(result.scalars().all())

    # Get MCP invocations
    stmt = select(MCPInvocation).where(MCPInvocation.run_id == run_id)
    result = await db.execute(stmt)
    mcp_invocations = list(result.scalars().all())

    # Get control decisions
    stmt = select(ControlDecision).where(ControlDecision.run_id == run_id)
    result = await db.execute(stmt)
    decisions = list(result.scalars().all())

    # Compute metrics
    total_agent_cost = sum(inv.cost for inv in agent_invocations)
    total_mcp_cost = sum(inv.cost for inv in mcp_invocations)
    total_cost = total_agent_cost + total_mcp_cost

    node_status_counts = {}
    for n in nodes:
        node_status_counts[n.status] = node_status_counts.get(n.status, 0) + 1

    return {
        "run_id": run_id,
        "run_status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "estimated_cost": run.estimated_cost,
        "actual_cost": total_cost,
        "nodes_total": len(nodes),
        "nodes_by_status": node_status_counts,
        "nodes": [
            {
                "id": n.id,
                "node_ref": n.node_ref,
                "node_type": n.node_type,
                "status": n.status,
                "order_index": n.order_index,
                "parallel_group": n.parallel_group,
            }
            for n in nodes
        ],
        "agent_invocations": len(agent_invocations),
        "agent_invocations_cost": total_agent_cost,
        "mcp_invocations": len(mcp_invocations),
        "mcp_invocations_cost": total_mcp_cost,
        "control_decisions": len(decisions),
        "control_denials": sum(1 for d in decisions if d.decision_type == "deny"),
    }


async def get_platform_metrics(db: AsyncSession) -> dict:
    """Aggregate platform-wide metrics."""
    # Runs by status
    stmt = select(Run.status, func.count(Run.id)).group_by(Run.status)
    result = await db.execute(stmt)
    runs_by_status = {row[0]: row[1] for row in result.all()}

    # Total costs
    stmt = select(func.sum(SubagentInvocation.cost))
    result = await db.execute(stmt)
    total_agent_cost = result.scalar() or 0

    stmt = select(func.sum(MCPInvocation.cost))
    result = await db.execute(stmt)
    total_mcp_cost = result.scalar() or 0

    # Control decisions
    stmt = (
        select(ControlDecision.decision_type, func.count(ControlDecision.id))
        .group_by(ControlDecision.decision_type)
    )
    result = await db.execute(stmt)
    decisions_by_type = {row[0]: row[1] for row in result.all()}

    # Audit events count
    stmt = select(func.count(AuditEvent.id))
    result = await db.execute(stmt)
    audit_events_total = result.scalar() or 0

    return {
        "runs_by_status": runs_by_status,
        "total_runs": sum(runs_by_status.values()),
        "total_agent_cost": float(total_agent_cost),
        "total_mcp_cost": float(total_mcp_cost),
        "total_cost": float(total_agent_cost + total_mcp_cost),
        "control_decisions_by_type": decisions_by_type,
        "audit_events_total": audit_events_total,
    }
