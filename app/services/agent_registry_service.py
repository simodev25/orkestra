"""Agent registry service — governed CRUD, filters, stats and draft save."""

from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import AgentDefinition
from app.schemas.agent import (
    AgentCreate,
    AgentRegistryStats,
    AgentUpdate,
    GeneratedAgentDraft,
)
from app.services import obot_catalog_service
from app.services.event_service import emit_event
from app.state_machines.agent_lifecycle_sm import AgentLifecycleStateMachine


_AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,99}$")


def _dedupe_str_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = raw.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def validate_agent_definition(data: AgentCreate) -> list[str]:
    errors: list[str] = []

    if not _AGENT_ID_RE.match(data.id):
        errors.append("id must match ^[a-z0-9][a-z0-9_-]{1,99}$")
    if not data.name or len(data.name.strip()) < 2:
        errors.append("name must be at least 2 characters")
    if not data.purpose or len(data.purpose.strip()) < 10:
        errors.append("purpose must be at least 10 characters")

    if data.prompt_content is not None and not data.prompt_content.strip():
        errors.append("prompt_content cannot be empty when provided")
    if data.skills_content is not None and not data.skills_content.strip():
        errors.append("skills_content cannot be empty when provided")

    return errors


def _apply_create_payload(agent: AgentDefinition, payload: AgentCreate) -> None:
    agent.name = payload.name
    agent.family = payload.family
    agent.purpose = payload.purpose
    agent.description = payload.description
    agent.skills = _dedupe_str_list(payload.skills)
    agent.selection_hints = payload.selection_hints
    agent.allowed_mcps = _dedupe_str_list(payload.allowed_mcps)
    agent.forbidden_effects = _dedupe_str_list(payload.forbidden_effects)
    agent.input_contract_ref = payload.input_contract_ref
    agent.output_contract_ref = payload.output_contract_ref
    agent.criticality = payload.criticality
    agent.cost_profile = payload.cost_profile
    agent.limitations = _dedupe_str_list(payload.limitations)
    agent.prompt_ref = payload.prompt_ref
    agent.prompt_content = payload.prompt_content
    agent.skills_ref = payload.skills_ref
    agent.skills_content = payload.skills_content
    agent.version = payload.version
    agent.status = payload.status
    agent.owner = payload.owner
    agent.last_test_status = payload.last_test_status
    agent.last_validated_at = payload.last_validated_at
    agent.usage_count = payload.usage_count


async def create_agent(db: AsyncSession, data: AgentCreate) -> AgentDefinition:
    errors = validate_agent_definition(data)
    if errors:
        raise ValueError(f"Validation errors: {'; '.join(errors)}")

    existing = await db.get(AgentDefinition, data.id)
    if existing:
        raise ValueError(f"Agent {data.id} already exists")

    agent = AgentDefinition(id=data.id)
    _apply_create_payload(agent, data)

    db.add(agent)
    await db.flush()
    await emit_event(
        db,
        "agent.registered",
        "system",
        "agent_registry",
        payload={"agent_id": agent.id, "status": agent.status},
    )
    return agent


async def update_agent(db: AsyncSession, agent_id: str, data: AgentUpdate) -> AgentDefinition:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    updates = data.model_dump(exclude_none=True)
    if "name" in updates and len(updates["name"].strip()) < 2:
        raise ValueError("name must be at least 2 characters")
    if "purpose" in updates and len(updates["purpose"].strip()) < 10:
        raise ValueError("purpose must be at least 10 characters")

    list_fields = {"skills", "allowed_mcps", "forbidden_effects", "limitations"}
    for field, value in updates.items():
        if field in list_fields:
            setattr(agent, field, _dedupe_str_list(value))
            continue
        if field in {"prompt_content", "skills_content"} and isinstance(value, str):
            if not value.strip():
                raise ValueError(f"{field} cannot be empty")
        setattr(agent, field, value)

    await db.flush()
    await emit_event(
        db,
        "agent.updated",
        "system",
        "agent_registry",
        payload={"agent_id": agent.id},
    )
    return agent


async def update_agent_status(
    db: AsyncSession,
    agent_id: str,
    new_status: str,
    reason: str = "",
) -> AgentDefinition:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    sm = AgentLifecycleStateMachine(agent.status)
    if not sm.transition(new_status, reason=reason):
        raise ValueError(f"Cannot transition agent from {agent.status} to {new_status}")
    agent.status = sm.state
    await emit_event(
        db,
        f"agent.{new_status}",
        "system",
        "agent_registry",
        payload={"agent_id": agent.id},
    )
    return agent


def _workflow_matches(agent: AgentDefinition, workflow_id: str) -> bool:
    hints = agent.selection_hints or {}
    if not isinstance(hints, dict):
        return False
    for key in ("workflow_ids", "preferred_workflows", "allowed_workflows"):
        value = hints.get(key)
        if isinstance(value, list) and workflow_id in value:
            return True
        if isinstance(value, str) and workflow_id == value:
            return True
    return False


def _matches_text(agent: AgentDefinition, q: str) -> bool:
    haystacks = [
        agent.id,
        agent.name,
        agent.family,
        agent.purpose,
        agent.description or "",
        " ".join(agent.skills or []),
        " ".join(agent.allowed_mcps or []),
    ]
    low_q = q.lower()
    return any(low_q in h.lower() for h in haystacks)


async def list_agents(
    db: AsyncSession,
    *,
    family: str | None = None,
    status: str | None = None,
    criticality: str | None = None,
    cost_profile: str | None = None,
    q: str | None = None,
    mcp_id: str | None = None,
    workflow_id: str | None = None,
    used_in_workflow_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentDefinition]:
    stmt = select(AgentDefinition)
    if family and family != "all":
        stmt = stmt.where(AgentDefinition.family == family)
    if status and status != "all":
        stmt = stmt.where(AgentDefinition.status == status)
    if criticality and criticality != "all":
        stmt = stmt.where(AgentDefinition.criticality == criticality)
    if cost_profile and cost_profile != "all":
        stmt = stmt.where(AgentDefinition.cost_profile == cost_profile)

    result = await db.execute(stmt.order_by(AgentDefinition.name))
    items = list(result.scalars().all())

    if q:
        items = [a for a in items if _matches_text(a, q)]
    if mcp_id:
        items = [a for a in items if mcp_id in (a.allowed_mcps or [])]
    if used_in_workflow_only and workflow_id:
        items = [a for a in items if _workflow_matches(a, workflow_id)]
    elif workflow_id:
        # Keep workflow_id as soft context without forcing filter when toggle is off.
        pass

    return items[offset : offset + limit]


async def get_agent(db: AsyncSession, agent_id: str) -> AgentDefinition | None:
    return await db.get(AgentDefinition, agent_id)


async def delete_agent(db: AsyncSession, agent_id: str) -> None:
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    if agent.status == "active":
        raise ValueError("Cannot delete an active agent. Disable or deprecate it first.")

    await db.delete(agent)
    await db.flush()
    await emit_event(
        db,
        "agent.deleted",
        "system",
        "agent_registry",
        payload={"agent_id": agent_id},
    )


async def get_registry_stats(db: AsyncSession, workflow_id: str | None = None) -> AgentRegistryStats:
    result = await db.execute(select(AgentDefinition))
    items = list(result.scalars().all())
    tested_like_status = {"tested", "registered", "active", "deprecated", "disabled", "archived"}

    current_workflow_agents = 0
    if workflow_id:
        current_workflow_agents = sum(1 for a in items if _workflow_matches(a, workflow_id))

    return AgentRegistryStats(
        total_agents=len(items),
        active_agents=sum(1 for a in items if a.status == "active"),
        tested_agents=sum(
            1
            for a in items
            if a.status in tested_like_status or (a.last_test_status and a.last_test_status != "not_tested")
        ),
        deprecated_agents=sum(1 for a in items if a.status == "deprecated"),
        current_workflow_agents=current_workflow_agents,
    )


async def available_mcp_summaries(db: AsyncSession) -> list[dict[str, str | bool]]:
    items = await obot_catalog_service.list_catalog_items(db)
    return [
        {
            "id": item.obot_server.id,
            "name": item.obot_server.name,
            "purpose": item.obot_server.purpose,
            "effect_type": item.obot_server.effect_type,
            "criticality": item.obot_server.criticality,
            "approval_required": item.obot_server.approval_required,
            "obot_state": item.obot_state,
            "orkestra_state": item.orkestra_state,
        }
        for item in items
    ]


async def save_generated_draft(db: AsyncSession, draft: GeneratedAgentDraft) -> AgentDefinition:
    errors: list[str] = []

    if draft.status not in {"draft", "designed"}:
        errors.append("status must be draft or designed")
    if not _AGENT_ID_RE.match(draft.agent_id):
        errors.append("agent_id format is invalid")
    if not draft.name.strip():
        errors.append("name is required")
    if not draft.purpose.strip():
        errors.append("purpose is required")
    if not draft.skills:
        errors.append("at least one skill is required")
    if not draft.prompt_content.strip():
        errors.append("prompt_content is required")
    if not draft.skills_content.strip():
        errors.append("skills_content is required")
    if not draft.limitations:
        errors.append("at least one limitation is required")

    available_mcps = await available_mcp_summaries(db)
    available_ids = {str(m["id"]) for m in available_mcps}
    unknown_mcps = [m for m in draft.allowed_mcps if m not in available_ids]
    if unknown_mcps:
        errors.append(f"allowed_mcps contain unknown ids: {', '.join(unknown_mcps)}")

    if errors:
        raise ValueError(f"Draft validation errors: {'; '.join(errors)}")

    payload = AgentCreate(
        id=draft.agent_id,
        name=draft.name,
        family=draft.family,
        purpose=draft.purpose,
        description=draft.description,
        skills=draft.skills,
        selection_hints=draft.selection_hints,
        allowed_mcps=draft.allowed_mcps,
        forbidden_effects=draft.forbidden_effects,
        input_contract_ref=draft.input_contract_ref,
        output_contract_ref=draft.output_contract_ref,
        criticality=draft.criticality,
        cost_profile=draft.cost_profile,
        limitations=draft.limitations,
        prompt_content=draft.prompt_content,
        skills_content=draft.skills_content,
        owner=draft.owner,
        version=draft.version,
        status="draft" if draft.status == "designed" else draft.status,
    )

    return await create_agent(db, payload)
