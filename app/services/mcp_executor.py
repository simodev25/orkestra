"""MCP executor -- invokes MCPs with governance, real tool execution with fallback."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invocation import MCPInvocation
from app.models.registry import MCPDefinition, AgentDefinition
from app.services.event_service import emit_event
from app.services.mcp_tool_registry import get_tools_for_mcp

logger = logging.getLogger(__name__)


async def invoke_mcp(
    db: AsyncSession,
    run_id: str,
    mcp_id: str,
    calling_agent_id: str,
    subagent_invocation_id: str | None = None,
    tool_action: str | None = None,
    tool_kwargs: dict | None = None,
) -> MCPInvocation:
    """Invoke an MCP with allowlist enforcement and real tool execution."""
    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found in registry")

    if mcp.status not in ("active", "degraded"):
        raise ValueError(f"MCP {mcp_id} is not available (status: {mcp.status})")

    # Allowlist enforcement
    agent = await db.get(AgentDefinition, calling_agent_id)
    if agent:
        allowed_mcps = agent.allowed_mcps or []
        if allowed_mcps and mcp_id not in allowed_mcps:
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

    # Try real MCP tool execution
    start_time = datetime.now(timezone.utc)
    try:
        result = await _execute_mcp_tool(mcp_id, tool_action, tool_kwargs or {})
        elapsed_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        inv.status = "completed"
        inv.latency_ms = elapsed_ms
        inv.cost = 0.02
        if result is not None:
            inv.output_summary = result[:200] if isinstance(result, str) else str(result)[:200]
        inv.ended_at = datetime.now(timezone.utc)

        await emit_event(db, "mcp.completed", "runtime", "mcp_executor",
                         run_id=run_id,
                         payload={"mcp_id": mcp_id, "mode": "real", "latency_ms": elapsed_ms})
        await db.flush()
        return inv
    except Exception as exc:
        inv.status = "failed"
        inv.latency_ms = 0
        inv.cost = 0.0
        inv.output_summary = f"MCP {mcp_id} execution failed: {exc}"
        inv.ended_at = datetime.now(timezone.utc)

        await emit_event(db, "mcp.failed", "runtime", "mcp_executor",
                         run_id=run_id,
                         payload={"mcp_id": mcp_id, "error": str(exc)})

        await db.flush()
        return inv


async def _execute_mcp_tool(mcp_id: str, action: str | None, kwargs: dict) -> str | None:
    """Execute a real MCP tool function. Returns result string or None."""
    tool_list = get_tools_for_mcp(mcp_id)
    if not tool_list:
        return None

    # Build a name-keyed dict for action lookup
    mcp_tools = {fn.__name__: fn for fn in tool_list}
    # Pick the action or default to first tool
    if action and action in mcp_tools:
        tool_func = mcp_tools[action]
    else:
        tool_func = tool_list[0]

    result = await tool_func(**kwargs)

    # Extract text from ToolResponse
    if hasattr(result, "content"):
        texts = []
        for block in result.content:
            if isinstance(block, dict):
                texts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else str(result)
    return str(result)
