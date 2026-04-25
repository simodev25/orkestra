"""MCP executor -- invokes MCPs with governance, real tool execution with fallback.

Supports both local Python tools (via mcp_tool_registry) and remote MCP servers
(via Obot catalog + HttpStatelessClient).  When local tools are not registered
for a given mcp_id, the executor resolves the MCP endpoint URL from Obot and
connects to the remote server to list and invoke tools.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invocation import MCPInvocation
from app.models.registry import MCPDefinition, AgentDefinition
from app.services.event_service import emit_event
from app.services.mcp_tool_registry import get_tools_for_mcp
from app.services.mcp_compat import apply_mcp_patches

logger = logging.getLogger(__name__)

# Ensure MCP SDK patches are applied for this execution path too.
apply_mcp_patches()


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
    """Execute a real MCP tool function. Returns result string or None.

    Resolution order:
    1. Local Python tools registered in mcp_tool_registry
    2. Remote MCP server resolved from Obot catalog (via HttpStatelessClient)
    """
    # --- 1. Try local tools first ---
    tool_list = get_tools_for_mcp(mcp_id)
    if tool_list:
        mcp_tools = {fn.__name__: fn for fn in tool_list}
        if action and action in mcp_tools:
            tool_func = mcp_tools[action]
        else:
            tool_func = tool_list[0]

        result = await tool_func(**kwargs)
        return _extract_tool_result(result)

    # --- 2. Fallback: remote MCP via Obot ---
    return await _execute_remote_mcp_tool(mcp_id, action, kwargs)


async def _execute_remote_mcp_tool(mcp_id: str, action: str | None, kwargs: dict) -> str | None:
    """Connect to a remote MCP server via Obot and execute a tool.

    Resolves the MCP endpoint URL from the Obot catalog, connects via
    HttpStatelessClient (same pattern as agent_factory), lists available tools,
    and invokes the requested action.

    Returns the tool result as a string, or None if the MCP cannot be resolved.
    """
    try:
        from app.services.obot_catalog_service import fetch_obot_server_by_id
    except ImportError:
        logger.warning("obot_catalog_service not available — cannot resolve remote MCP %s", mcp_id)
        return None

    # Resolve endpoint URL from Obot
    try:
        server, source = await fetch_obot_server_by_id(mcp_id)
    except Exception as exc:
        logger.warning("Failed to resolve MCP %s from Obot: %s", mcp_id, exc)
        return None

    if not server:
        logger.info("MCP %s not found in Obot catalog (source=%s)", mcp_id, source)
        return None

    endpoint_url = server.mcp_endpoint_url
    if not endpoint_url:
        logger.warning("MCP %s (%s) has no endpoint URL — cannot connect", mcp_id, server.name)
        return None

    # Connect to remote MCP server
    try:
        from agentscope.mcp import HttpStatelessClient
    except ImportError:
        logger.warning("agentscope.mcp.HttpStatelessClient not available — cannot connect to remote MCP %s", mcp_id)
        return None

    from app.core.config import get_settings
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.OBOT_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OBOT_API_KEY}"

    try:
        mcp_client = HttpStatelessClient(
            name=mcp_id,
            transport="streamable_http",
            url=endpoint_url,
            timeout=30,
            headers=headers,
        )

        # List available tools
        mcp_tools = await mcp_client.list_tools()
        if not mcp_tools:
            logger.warning("MCP %s (%s): no tools available at %s", mcp_id, server.name, endpoint_url)
            return None

        logger.info("MCP %s (%s): %d tools found at %s", mcp_id, server.name, len(mcp_tools), endpoint_url)

        # Pick the requested action or default to first tool
        tool_name = action
        if not tool_name:
            tool_name = mcp_tools[0].name
        else:
            available_names = [t.name for t in mcp_tools]
            if tool_name not in available_names:
                logger.warning(
                    "MCP %s: requested tool '%s' not found. Available: %s",
                    mcp_id, tool_name, available_names,
                )
                return None

        # Get callable and invoke
        tool_func = await mcp_client.get_callable_function(tool_name, wrap_tool_result=False)
        result = await tool_func(**kwargs)
        return _extract_tool_result(result)

    except Exception as exc:
        # Unwrap ExceptionGroup for clearer error messages
        real_err = _format_mcp_exception(exc)
        logger.error("MCP %s remote execution failed: %s", mcp_id, real_err)
        raise RuntimeError(f"Remote MCP {mcp_id} ({server.name}) execution failed: {real_err}") from exc


def _format_mcp_exception(e: Exception) -> str:
    """Unwrap BaseExceptionGroup to extract the real inner exceptions."""
    if hasattr(e, "exceptions"):
        parts = []
        for inner in e.exceptions:  # type: ignore[attr-defined]
            parts.append(_format_mcp_exception(inner))
        return f"[{type(e).__name__}] " + " | ".join(parts)
    return f"{type(e).__name__}: {e}"


def _extract_tool_result(result) -> str:
    """Extract text content from a tool result (ToolResponse or plain value)."""
    if hasattr(result, "content"):
        texts = []
        for block in result.content:
            if isinstance(block, dict):
                texts.append(block.get("text", ""))
            elif hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts) if texts else str(result)
    return str(result)
