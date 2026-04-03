"""MCP registry service — CRUD and lifecycle."""

from sqlalchemy import select
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
) -> list[MCPDefinition]:
    stmt = select(MCPDefinition)
    if effect_type:
        stmt = stmt.where(MCPDefinition.effect_type == effect_type)
    if status:
        stmt = stmt.where(MCPDefinition.status == status)
    if criticality:
        stmt = stmt.where(MCPDefinition.criticality == criticality)
    stmt = stmt.order_by(MCPDefinition.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_mcp(db: AsyncSession, mcp_id: str) -> MCPDefinition | None:
    return await db.get(MCPDefinition, mcp_id)
