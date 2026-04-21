"""Guarded MCP executor — AOP wrapper adding forbidden-effects enforcement."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invocation import MCPInvocation
from app.models.registry import AgentDefinition
from app.services.effect_classifier import get_classifier
from app.services.event_service import emit_event
from app.services.mcp_executor import invoke_mcp

logger = logging.getLogger(__name__)


async def guarded_invoke_mcp(
    db: AsyncSession,
    run_id: str,
    mcp_id: str,
    calling_agent_id: str,
    subagent_invocation_id: str | None = None,
    tool_action: str | None = None,
    tool_kwargs: dict | None = None,
    run_effect_overrides: list[str] | None = None,
) -> MCPInvocation:
    """Invoke an MCP with forbidden-effects enforcement before delegating to invoke_mcp.

    If the calling agent has forbidden_effects configured and the tool_action is
    classified into one of those effects (minus any run-level overrides), the call
    is blocked immediately: a denied MCPInvocation is persisted and an event emitted.
    Otherwise, the call is delegated unchanged to invoke_mcp().
    """
    # [1] Fetch agent's forbidden_effects
    agent = await db.get(AgentDefinition, calling_agent_id)
    if agent is None:
        logger.warning(
            "[guarded_invoke_mcp] Unknown calling_agent_id=%s — no forbidden_effects enforced",
            calling_agent_id,
        )
    forbidden = set(agent.forbidden_effects or []) if agent else set()

    # [2] Only classify if there are forbidden_effects AND a tool_action
    if forbidden and tool_action:
        effects = await get_classifier().classify(tool_action, tool_kwargs or {})

        # [3] Run-level override: remove effects explicitly allowed for this run
        overrides = set(run_effect_overrides or [])
        effective_forbidden = forbidden - overrides
        blocked = [e for e in effects if e in effective_forbidden]

        if blocked:
            inv = MCPInvocation(
                run_id=run_id,
                subagent_invocation_id=subagent_invocation_id,
                mcp_id=mcp_id,
                calling_agent_id=calling_agent_id,
                effect_type=",".join(blocked),  # CSV: "write,act"
                status="denied",
                approval_required=False,
            )
            db.add(inv)
            await db.flush()
            await emit_event(
                db,
                "mcp.denied",
                "runtime",
                "guarded_mcp_executor",
                run_id=run_id,
                payload={
                    "mcp_id": mcp_id,
                    "agent_id": calling_agent_id,
                    "reason": "forbidden_effect",
                    "effects": blocked,
                },
            )
            return inv

    # [4] No forbidden effects triggered — delegate to existing engine
    return await invoke_mcp(
        db,
        run_id,
        mcp_id,
        calling_agent_id,
        subagent_invocation_id,
        tool_action,
        tool_kwargs,
    )
