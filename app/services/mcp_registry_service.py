"""MCP registry service — CRUD and lifecycle."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import MCPDefinition
from app.models.enums import MCPEffectType
from app.schemas.mcp import MCPCreate
from app.state_machines.mcp_lifecycle_sm import MCPLifecycleStateMachine
from app.services.event_service import emit_event


def validate_mcp_definition(data: MCPCreate) -> list[str]:
    errors = []
    valid_effects = [e.value for e in MCPEffectType]
    if data.effect_type not in valid_effects:
        errors.append(f"effect_type must be one of {valid_effects}")
    return errors


async def create_mcp(db: AsyncSession, data: MCPCreate) -> MCPDefinition:
    errors = validate_mcp_definition(data)
    if errors:
        raise ValueError(f"Validation errors: {'; '.join(errors)}")

    existing = await db.get(MCPDefinition, data.id)
    if existing:
        raise ValueError(f"MCP {data.id} already exists")

    mcp = MCPDefinition(
        id=data.id, name=data.name, purpose=data.purpose, description=data.description,
        effect_type=data.effect_type, input_contract_ref=data.input_contract_ref,
        output_contract_ref=data.output_contract_ref, allowed_agents=data.allowed_agents,
        criticality=data.criticality, timeout_seconds=data.timeout_seconds,
        retry_policy=data.retry_policy, cost_profile=data.cost_profile,
        approval_required=data.approval_required, audit_required=data.audit_required,
        version=data.version, owner=data.owner,
    )
    db.add(mcp)
    await db.flush()
    await emit_event(db, "mcp.registered", "system", "mcp_registry", payload={"mcp_id": mcp.id})
    return mcp


async def update_mcp_status(db: AsyncSession, mcp_id: str, new_status: str, reason: str = "") -> MCPDefinition:
    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")
    sm = MCPLifecycleStateMachine(mcp.status)
    if not sm.transition(new_status, reason=reason):
        raise ValueError(f"Cannot transition MCP from {mcp.status} to {new_status}")
    mcp.status = sm.state
    await emit_event(db, f"mcp.{new_status}", "system", "mcp_registry", payload={"mcp_id": mcp.id})
    return mcp


async def list_mcps(
    db: AsyncSession, effect_type: str | None = None, status: str | None = None,
    criticality: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[list[MCPDefinition], int]:
    stmt = select(MCPDefinition)
    if effect_type:
        stmt = stmt.where(MCPDefinition.effect_type == effect_type)
    if status:
        stmt = stmt.where(MCPDefinition.status == status)
    if criticality:
        stmt = stmt.where(MCPDefinition.criticality == criticality)
    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0
    paged_stmt = stmt.order_by(MCPDefinition.name).offset(offset).limit(limit)
    result = await db.execute(paged_stmt)
    return list(result.scalars().all()), total


async def get_mcp(db: AsyncSession, mcp_id: str) -> MCPDefinition | None:
    return await db.get(MCPDefinition, mcp_id)


async def update_mcp(db: AsyncSession, mcp_id: str, data) -> MCPDefinition:
    """Update MCP fields (not status — that goes through lifecycle)."""
    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    update_data = data.model_dump(exclude_none=True) if hasattr(data, 'model_dump') else data
    if "effect_type" in update_data:
        valid_effects = [e.value for e in MCPEffectType]
        if update_data["effect_type"] not in valid_effects:
            raise ValueError(f"effect_type must be one of {valid_effects}")

    for key, value in update_data.items():
        if hasattr(mcp, key):
            setattr(mcp, key, value)

    await db.flush()
    await emit_event(db, "mcp.updated", "system", "mcp_registry", payload={"mcp_id": mcp.id})
    return mcp


async def get_catalog_stats(db: AsyncSession) -> dict:
    """Get aggregate stats for the MCP catalog."""
    stmt = select(MCPDefinition)
    result = await db.execute(stmt)
    all_mcps = list(result.scalars().all())

    return {
        "total": len(all_mcps),
        "active": sum(1 for m in all_mcps if m.status == "active"),
        "degraded": sum(1 for m in all_mcps if m.status == "degraded"),
        "disabled": sum(1 for m in all_mcps if m.status == "disabled"),
        "critical": sum(1 for m in all_mcps if m.criticality == "high"),
        "approval_required": sum(1 for m in all_mcps if m.approval_required),
        "healthy": sum(1 for m in all_mcps if m.status in ("active",)),
    }


async def get_mcp_health(db: AsyncSession, mcp_id: str) -> dict:
    """Get health info for an MCP based on invocation history."""
    from app.models.invocation import MCPInvocation
    from sqlalchemy import func

    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    # Get invocation stats
    stmt = select(MCPInvocation).where(MCPInvocation.mcp_id == mcp_id)
    result = await db.execute(stmt)
    invocations = list(result.scalars().all())

    total = len(invocations)
    completed = [i for i in invocations if i.status == "completed"]
    failed = [i for i in invocations if i.status == "failed"]

    avg_latency = sum(i.latency_ms or 0 for i in completed) / max(len(completed), 1)
    failure_rate = len(failed) / max(total, 1)

    last_success = max((i.ended_at for i in completed if i.ended_at), default=None)
    last_failure = max((i.ended_at for i in failed if i.ended_at), default=None)

    recent_errors = [
        i.output_summary or "Unknown error" for i in sorted(failed, key=lambda x: x.created_at, reverse=True)[:5]
    ]

    return {
        "mcp_id": mcp_id,
        "status": mcp.status,
        "healthy": mcp.status in ("active",) and failure_rate < 0.5,
        "last_check_at": None,
        "last_success_at": last_success.isoformat() if last_success else None,
        "last_failure_at": last_failure.isoformat() if last_failure else None,
        "avg_latency_ms": round(avg_latency, 1),
        "failure_rate": round(failure_rate, 3),
        "total_invocations": total,
        "recent_errors": recent_errors,
    }


async def get_mcp_usage(db: AsyncSession, mcp_id: str) -> dict:
    """Get usage stats for an MCP."""
    from app.models.invocation import MCPInvocation

    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    stmt = select(MCPInvocation).where(MCPInvocation.mcp_id == mcp_id)
    result = await db.execute(stmt)
    invocations = list(result.scalars().all())

    total = len(invocations)
    total_cost = sum(i.cost for i in invocations)
    completed = [i for i in invocations if i.status == "completed"]
    avg_latency = sum(i.latency_ms or 0 for i in completed) / max(len(completed), 1)

    # Agents using this MCP
    from app.models.registry import AgentDefinition
    stmt_agents = select(AgentDefinition)
    result_agents = await db.execute(stmt_agents)
    all_agents = list(result_agents.scalars().all())
    agents_using = [a.id for a in all_agents if a.allowed_mcps and mcp_id in a.allowed_mcps]

    # Invocations by status
    by_status = {}
    for inv in invocations:
        by_status[inv.status] = by_status.get(inv.status, 0) + 1

    return {
        "mcp_id": mcp_id,
        "total_invocations": total,
        "total_cost": round(total_cost, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "avg_cost": round(total_cost / max(total, 1), 4),
        "agents_using": agents_using,
        "invocations_by_status": by_status,
    }


async def test_mcp(db: AsyncSession, mcp_id: str, tool_action: str | None = None, tool_kwargs: dict | None = None) -> dict:
    """Test an MCP by invoking it and recording the result."""
    from app.services.mcp_executor import _execute_mcp_tool
    from datetime import datetime, timezone
    import time

    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    start = time.monotonic()
    try:
        result = await _execute_mcp_tool(mcp_id, tool_action, tool_kwargs or {})
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "mcp_id": mcp_id,
            "success": True,
            "latency_ms": elapsed_ms,
            "output": result[:2000] if result else "No output",
            "error": None,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "mcp_id": mcp_id,
            "success": False,
            "latency_ms": elapsed_ms,
            "output": None,
            "error": str(e),
        }
