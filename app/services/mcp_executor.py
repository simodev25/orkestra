"""MCP executor — invokes MCPs with governance checks."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invocation import MCPInvocation
from app.models.registry import MCPDefinition, AgentDefinition
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


async def invoke_mcp(
    db: AsyncSession,
    run_id: str,
    mcp_id: str,
    calling_agent_id: str,
    subagent_invocation_id: str | None = None,
) -> MCPInvocation:
    """Invoke an MCP with allowlist enforcement.

    In Phase 2, this is a simulated invocation.
    """
    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found in registry")

    # Check MCP is active or degraded
    if mcp.status not in ("active", "degraded"):
        raise ValueError(f"MCP {mcp_id} is not available (status: {mcp.status})")

    # Allowlist enforcement
    agent = await db.get(AgentDefinition, calling_agent_id)
    if agent:
        allowed_mcps = agent.allowed_mcps or []
        if allowed_mcps and mcp_id not in allowed_mcps:
            # Create denied invocation
            inv = MCPInvocation(
                run_id=run_id,
                subagent_invocation_id=subagent_invocation_id,
                mcp_id=mcp_id,
                effect_type=mcp.effect_type,
                status="denied",
                approval_required=mcp.approval_required,
            )
            db.add(inv)
            await db.flush()
            await emit_event(db, "mcp.denied", "runtime", "mcp_executor",
                             run_id=run_id,
                             payload={"mcp_id": mcp_id, "agent_id": calling_agent_id,
                                      "reason": "not in agent allowlist"})
            return inv

    # Create invocation record
    inv = MCPInvocation(
        run_id=run_id,
        subagent_invocation_id=subagent_invocation_id,
        mcp_id=mcp_id,
        mcp_version=mcp.version,
        effect_type=mcp.effect_type,
        status="running",
        approval_required=mcp.approval_required,
        started_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    await db.flush()

    await emit_event(db, "mcp.requested", "runtime", "mcp_executor",
                     run_id=run_id, payload={"mcp_id": mcp_id})

    # Simulated execution
    inv.status = "completed"
    inv.latency_ms = 120
    inv.cost = 0.02
    inv.output_summary = f"MCP {mcp_id} completed (simulated)"
    inv.ended_at = datetime.now(timezone.utc)

    await emit_event(db, "mcp.completed", "runtime", "mcp_executor",
                     run_id=run_id, payload={"mcp_id": mcp_id, "latency_ms": 120})

    await db.flush()
    return inv
