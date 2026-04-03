"""Agent registry service — CRUD and lifecycle."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.schemas.agent import AgentCreate
from app.state_machines.agent_lifecycle_sm import AgentLifecycleStateMachine
from app.services.event_service import emit_event


def validate_agent_definition(data: AgentCreate) -> list[str]:
    errors = []
    if not data.purpose or len(data.purpose.strip()) < 5:
        errors.append("purpose must be at least 5 characters")
    return errors


async def create_agent(db: AsyncSession, data: AgentCreate) -> AgentDefinition:
    errors = validate_agent_definition(data)
    if errors:
        raise ValueError(f"Validation errors: {'; '.join(errors)}")

    existing = await db.get(AgentDefinition, data.id)
    if existing:
        raise ValueError(f"Agent {data.id} already exists")

    agent = AgentDefinition(
        id=data.id, name=data.name, family=data.family, purpose=data.purpose,
        description=data.description, skills=data.skills, selection_hints=data.selection_hints,
        allowed_mcps=data.allowed_mcps, forbidden_effects=data.forbidden_effects,
        input_contract_ref=data.input_contract_ref, output_contract_ref=data.output_contract_ref,
        criticality=data.criticality, cost_profile=data.cost_profile,
        limitations=data.limitations, prompt_ref=data.prompt_ref,
        skills_ref=data.skills_ref, version=data.version, owner=data.owner,
    )
    db.add(agent)
    await db.flush()
    await emit_event(db, "agent.registered", "system", "agent_registry", payload={"agent_id": agent.id})
    return agent


async def update_agent_status(db: AsyncSession, agent_id: str, new_status: str, reason: str = "") -> AgentDefinition:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    sm = AgentLifecycleStateMachine(agent.status)
    if not sm.transition(new_status, reason=reason):
        raise ValueError(f"Cannot transition agent from {agent.status} to {new_status}")
    agent.status = sm.state
    await emit_event(db, f"agent.{new_status}", "system", "agent_registry", payload={"agent_id": agent.id})
    return agent


async def list_agents(
    db: AsyncSession, family: str | None = None, status: str | None = None,
    criticality: str | None = None, limit: int = 50, offset: int = 0,
) -> list[AgentDefinition]:
    stmt = select(AgentDefinition)
    if family:
        stmt = stmt.where(AgentDefinition.family == family)
    if status:
        stmt = stmt.where(AgentDefinition.status == status)
    if criticality:
        stmt = stmt.where(AgentDefinition.criticality == criticality)
    stmt = stmt.order_by(AgentDefinition.name).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_agent(db: AsyncSession, agent_id: str) -> AgentDefinition | None:
    return await db.get(AgentDefinition, agent_id)
