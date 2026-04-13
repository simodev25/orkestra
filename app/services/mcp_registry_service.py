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

    # Snapshot current state to history before applying changes
    from app.models.mcp_history import MCPDefinitionHistory

    history = MCPDefinitionHistory(
        mcp_id=mcp.id,
        snapshot={
            "name": mcp.name,
            "purpose": mcp.purpose,
            "description": mcp.description,
            "effect_type": mcp.effect_type,
            "input_contract_ref": mcp.input_contract_ref,
            "output_contract_ref": mcp.output_contract_ref,
            "allowed_agents": mcp.allowed_agents,
            "criticality": mcp.criticality,
            "timeout_seconds": mcp.timeout_seconds,
            "retry_policy": mcp.retry_policy,
            "cost_profile": mcp.cost_profile,
            "approval_required": mcp.approval_required,
            "audit_required": mcp.audit_required,
            "status": mcp.status,
            "owner": mcp.owner,
        },
        version=mcp.version or "1.0.0",
    )
    db.add(history)

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
    from sqlalchemy import case

    stmt = select(
        func.count().label("total"),
        func.count(case((MCPDefinition.status == "active", 1))).label("active"),
        func.count(case((MCPDefinition.status == "degraded", 1))).label("degraded"),
        func.count(case((MCPDefinition.status == "disabled", 1))).label("disabled"),
        func.count(case((MCPDefinition.criticality == "high", 1))).label("critical"),
        func.count(case((MCPDefinition.approval_required == True, 1))).label("approval_required"),  # noqa: E712
        func.count(case((MCPDefinition.status == "active", 1))).label("healthy"),
    ).select_from(MCPDefinition)
    row = (await db.execute(stmt)).one()
    return {
        "total": row.total,
        "active": row.active,
        "degraded": row.degraded,
        "disabled": row.disabled,
        "critical": row.critical,
        "approval_required": row.approval_required,
        "healthy": row.healthy,
    }


async def get_mcp_health(db: AsyncSession, mcp_id: str) -> dict:
    """Get health info for an MCP based on invocation history."""
    from app.models.invocation import MCPInvocation
    from sqlalchemy import case

    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    # Aggregate stats in a single SQL query
    agg_stmt = select(
        func.count().label("total"),
        func.count(case((MCPInvocation.status == "completed", 1))).label("completed_count"),
        func.count(case((MCPInvocation.status == "failed", 1))).label("failed_count"),
        func.avg(
            case((MCPInvocation.status == "completed", MCPInvocation.latency_ms))
        ).label("avg_latency"),
        func.max(
            case((MCPInvocation.status == "completed", MCPInvocation.ended_at))
        ).label("last_success"),
        func.max(
            case((MCPInvocation.status == "failed", MCPInvocation.ended_at))
        ).label("last_failure"),
    ).where(MCPInvocation.mcp_id == mcp_id)
    agg = (await db.execute(agg_stmt)).one()

    total = agg.total or 0
    failed_count = agg.failed_count or 0
    avg_latency = float(agg.avg_latency or 0)
    failure_rate = failed_count / max(total, 1)

    # Recent errors: only the 5 most recent failed, select only needed columns
    from sqlalchemy import desc
    recent_stmt = (
        select(MCPInvocation.output_summary)
        .where(MCPInvocation.mcp_id == mcp_id, MCPInvocation.status == "failed")
        .order_by(desc(MCPInvocation.ended_at))
        .limit(5)
    )
    recent_errors = [
        row.output_summary or "Unknown error"
        for row in (await db.execute(recent_stmt)).all()
    ]

    last_success = agg.last_success
    last_failure = agg.last_failure

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
    from app.models.registry import AgentDefinition
    from sqlalchemy import case

    mcp = await db.get(MCPDefinition, mcp_id)
    if not mcp:
        raise ValueError(f"MCP {mcp_id} not found")

    # Aggregate invocation stats in SQL
    agg_stmt = select(
        func.count().label("total"),
        func.coalesce(func.sum(MCPInvocation.cost), 0).label("total_cost"),
        func.avg(
            case((MCPInvocation.status == "completed", MCPInvocation.latency_ms))
        ).label("avg_latency"),
    ).where(MCPInvocation.mcp_id == mcp_id)
    agg = (await db.execute(agg_stmt)).one()

    # Invocations by status using GROUP BY
    by_status_stmt = (
        select(MCPInvocation.status, func.count().label("cnt"))
        .where(MCPInvocation.mcp_id == mcp_id)
        .group_by(MCPInvocation.status)
    )
    by_status = {
        row.status: row.cnt
        for row in (await db.execute(by_status_stmt)).all()
    }

    # Agents using this MCP: filter with SQL JSONB contains
    agents_stmt = select(AgentDefinition.id).where(
        AgentDefinition.allowed_mcps.contains([mcp_id])
    )
    agents_using = [row.id for row in (await db.execute(agents_stmt)).all()]

    total = agg.total or 0
    total_cost = float(agg.total_cost or 0)
    avg_latency = float(agg.avg_latency or 0)

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
