"""Agent registry service — governed CRUD, filters, stats and draft save."""

from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.family import AgentSkill, FamilyDefinition
from app.models.registry import AgentDefinition
from app.schemas.agent import (
    AgentCreate,
    AgentRegistryStats,
    AgentUpdate,
    GeneratedAgentDraft,
)
from app.services import obot_catalog_service, skill_service
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


async def validate_agent_definition(db: AsyncSession, data: AgentCreate) -> list[str]:
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

    # Validate family_id exists and is active
    family = await db.get(FamilyDefinition, data.family_id)
    if not family:
        errors.append(f"family '{data.family_id}' does not exist")
    elif family.status != "active":
        errors.append(f"family '{data.family_id}' is not active (status: {family.status})")

    # Validate skill references against the DB registry
    if data.skill_ids:
        from app.models.skill import SkillDefinition
        skill_ids = _dedupe_str_list(data.skill_ids)
        _, unresolved = await skill_service.resolve_skills(db, skill_ids)
        for sid in unresolved:
            errors.append(f"agent references unknown skill_id: '{sid}'")

        # Validate that referenced skills are active
        for sid in skill_ids:
            if sid not in unresolved:
                skill_obj = await db.get(SkillDefinition, sid)
                if skill_obj and skill_obj.status != "active":
                    errors.append(f"skill '{sid}' is not active (status: {skill_obj.status})")

        # Validate skills are compatible with the declared family
        if not errors:
            incompatible = await skill_service.validate_skills_for_family(
                db, skill_ids, data.family_id
            )
            for sid in incompatible:
                errors.append(
                    f"skill '{sid}' is not allowed for family '{data.family_id}'"
                )

    return errors


async def _apply_create_payload(db: AsyncSession, agent: AgentDefinition, payload: AgentCreate) -> None:
    agent.name = payload.name
    agent.family_id = payload.family_id
    agent.purpose = payload.purpose
    agent.description = payload.description
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
    agent.soul_content = payload.soul_content
    agent.llm_provider = payload.llm_provider
    agent.llm_model = payload.llm_model
    agent.skills_ref = payload.skills_ref
    # Auto-generate skills_content from resolved skill_ids if not explicitly provided
    skill_ids = _dedupe_str_list(payload.skill_ids)
    if skill_ids and not payload.skills_content:
        agent.skills_content = await skill_service.build_skills_content(db, skill_ids)
    else:
        agent.skills_content = payload.skills_content
    agent.version = payload.version
    agent.status = payload.status
    agent.owner = payload.owner
    agent.last_test_status = "not_tested"
    agent.last_validated_at = None
    agent.usage_count = 0


async def _sync_agent_skills(db: AsyncSession, agent_id: str, skill_ids: list[str]) -> None:
    """Replace agent's AgentSkill rows with the given skill_ids list."""
    # Delete existing entries via ORM
    existing_result = await db.execute(
        select(AgentSkill).where(AgentSkill.agent_id == agent_id)
    )
    for row in existing_result.scalars().all():
        await db.delete(row)
    await db.flush()

    for sid in skill_ids:
        db.add(AgentSkill(agent_id=agent_id, skill_id=sid))
    await db.flush()


async def _get_agent_skill_ids(db: AsyncSession, agent_id: str) -> list[str]:
    """Return the list of skill_ids for an agent from the AgentSkill join table."""
    result = await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent_id)
    )
    return [row[0] for row in result.all()]


async def create_agent(db: AsyncSession, data: AgentCreate) -> AgentDefinition:
    errors = await validate_agent_definition(db, data)
    if errors:
        raise ValueError(f"Validation errors: {'; '.join(errors)}")

    existing = await db.get(AgentDefinition, data.id)
    if existing:
        raise ValueError(f"Agent {data.id} already exists")

    agent = AgentDefinition(id=data.id)
    await _apply_create_payload(db, agent, data)

    db.add(agent)
    await db.flush()

    # Sync AgentSkill join rows
    skill_ids = _dedupe_str_list(data.skill_ids)
    if skill_ids:
        await _sync_agent_skills(db, agent.id, skill_ids)

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

    # Snapshot current state to history before applying changes
    from app.models.history import AgentDefinitionHistory
    from app.services.version_utils import bump_patch

    current_skill_ids = await _get_agent_skill_ids(db, agent_id)
    history = AgentDefinitionHistory(
        agent_id=agent.id,
        name=agent.name,
        family_id=agent.family_id,
        purpose=agent.purpose,
        description=agent.description,
        skill_ids_snapshot=current_skill_ids,
        prompt_content=agent.prompt_content,
        skills_content=agent.skills_content,
        soul_content=agent.soul_content,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        selection_hints=agent.selection_hints,
        allowed_mcps=agent.allowed_mcps,
        forbidden_effects=agent.forbidden_effects,
        limitations=agent.limitations,
        criticality=agent.criticality,
        cost_profile=agent.cost_profile,
        version=agent.version or "1.0.0",
        status="superseded",
        owner=agent.owner,
        original_created_at=agent.created_at,
        original_updated_at=agent.updated_at,
    )
    db.add(history)

    updates = data.model_dump(exclude_none=True)

    # Version is auto-managed
    updates.pop("version", None)
    agent.version = bump_patch(agent.version or "1.0.0")
    if "name" in updates and len(updates["name"].strip()) < 2:
        raise ValueError("name must be at least 2 characters")
    if "purpose" in updates and len(updates["purpose"].strip()) < 10:
        raise ValueError("purpose must be at least 10 characters")

    # Validate new family_id if provided
    new_family_id = updates.get("family_id", agent.family_id)
    if "family_id" in updates:
        if not await db.get(FamilyDefinition, updates["family_id"]):
            raise ValueError(f"family '{updates['family_id']}' does not exist")

    # Validate skill_ids on update
    new_skill_ids: list[str] | None = None
    if "skill_ids" in updates:
        new_skill_ids = _dedupe_str_list(updates.pop("skill_ids"))
        _, unresolved = await skill_service.resolve_skills(db, new_skill_ids)
        if unresolved:
            raise ValueError(f"agent references unknown skill_ids: {unresolved}")
        # Validate skills are compatible with the family
        incompatible = await skill_service.validate_skills_for_family(
            db, new_skill_ids, new_family_id
        )
        if incompatible:
            raise ValueError(
                f"skills not allowed for family '{new_family_id}': {incompatible}"
            )

    list_fields = {"allowed_mcps", "forbidden_effects", "limitations"}
    for field, value in updates.items():
        if field in list_fields:
            setattr(agent, field, _dedupe_str_list(value))
            continue
        if field in {"prompt_content", "skills_content"} and isinstance(value, str):
            if not value.strip():
                raise ValueError(f"{field} cannot be empty")
        setattr(agent, field, value)

    # Sync AgentSkill join rows and regenerate skills_content only if not manually provided
    if new_skill_ids is not None:
        await _sync_agent_skills(db, agent_id, new_skill_ids)
        if "skills_content" not in updates:
            agent.skills_content = await skill_service.build_skills_content(db, new_skill_ids)

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


async def restore_agent(db: AsyncSession, agent_id: str, history_id: str) -> AgentDefinition:
    """Restore an agent to a previous version. Snapshots current state first."""
    from app.models.history import AgentDefinitionHistory
    from app.services.version_utils import bump_patch

    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise ValueError(f"Agent '{agent_id}' not found")

    history = await db.get(AgentDefinitionHistory, history_id)
    if not history or history.agent_id != agent_id:
        raise ValueError(f"History entry '{history_id}' not found for agent '{agent_id}'")

    # Snapshot current state first
    current_skill_ids = await _get_agent_skill_ids(db, agent_id)
    snapshot = AgentDefinitionHistory(
        agent_id=agent.id,
        name=agent.name,
        family_id=agent.family_id,
        purpose=agent.purpose,
        description=agent.description,
        skill_ids_snapshot=current_skill_ids,
        prompt_content=agent.prompt_content,
        skills_content=agent.skills_content,
        soul_content=agent.soul_content,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        selection_hints=agent.selection_hints,
        allowed_mcps=agent.allowed_mcps,
        forbidden_effects=agent.forbidden_effects,
        limitations=agent.limitations,
        criticality=agent.criticality,
        cost_profile=agent.cost_profile,
        version=agent.version or "1.0.0",
        status="superseded",
        owner=agent.owner,
        original_created_at=agent.created_at,
        original_updated_at=agent.updated_at,
    )
    db.add(snapshot)

    # Restore from history
    agent.name = history.name
    agent.family_id = history.family_id
    agent.purpose = history.purpose
    agent.description = history.description
    agent.prompt_content = history.prompt_content
    agent.skills_content = history.skills_content
    agent.soul_content = history.soul_content
    agent.llm_provider = history.llm_provider
    agent.llm_model = history.llm_model
    agent.selection_hints = history.selection_hints
    agent.allowed_mcps = history.allowed_mcps
    agent.forbidden_effects = history.forbidden_effects
    agent.limitations = history.limitations
    agent.criticality = history.criticality
    agent.cost_profile = history.cost_profile
    agent.owner = history.owner
    agent.version = bump_patch(agent.version or "1.0.0")

    # Restore skill_ids from snapshot
    await _sync_agent_skills(db, agent_id, history.skill_ids_snapshot or [])

    await db.flush()
    return agent


async def get_agent_history(db: AsyncSession, agent_id: str) -> list:
    """Return version history for an agent, most recent first."""
    from app.models.history import AgentDefinitionHistory
    result = await db.execute(
        select(AgentDefinitionHistory)
        .where(AgentDefinitionHistory.agent_id == agent_id)
        .order_by(AgentDefinitionHistory.replaced_at.desc())
    )
    return list(result.scalars().all())


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
        agent.family_id,
        agent.purpose,
        agent.description or "",
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
) -> tuple[list[AgentDefinition], int]:
    stmt = select(AgentDefinition).options(
        selectinload(AgentDefinition.family_rel),
        selectinload(AgentDefinition.agent_skills),
    )
    if family and family != "all":
        stmt = stmt.where(AgentDefinition.family_id == family)
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

    total = len(items)
    return items[offset : offset + limit], total


async def get_agent(db: AsyncSession, agent_id: str) -> AgentDefinition | None:
    stmt = (
        select(AgentDefinition)
        .where(AgentDefinition.id == agent_id)
        .options(
            selectinload(AgentDefinition.family_rel),
            selectinload(AgentDefinition.agent_skills),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


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
    items, _ = await obot_catalog_service.list_catalog_items(db, limit=100000)
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


async def available_skills(db: AsyncSession) -> list[str]:
    """Return a sorted list of unique skill_ids across all AgentSkill entries."""
    result = await db.execute(
        select(AgentSkill.skill_id).distinct()
    )
    return sorted(row[0] for row in result.all())


async def enrich_agent(db: AsyncSession, agent: AgentDefinition) -> dict:
    """Return a dict with full agent data including family object and resolved skills."""
    # Load family
    family = await db.get(FamilyDefinition, agent.family_id)

    # Load skill_ids from join table
    sk_result = await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent.id)
    )
    skill_ids = [row[0] for row in sk_result.all()]

    # Resolve skills
    resolved, _ = await skill_service.resolve_skills(db, skill_ids)

    return {
        "id": agent.id,
        "name": agent.name,
        "family_id": agent.family_id,
        "family": family,
        "purpose": agent.purpose,
        "description": agent.description,
        "skill_ids": skill_ids,
        "skills_resolved": resolved,
        "selection_hints": agent.selection_hints,
        "allowed_mcps": agent.allowed_mcps,
        "forbidden_effects": agent.forbidden_effects,
        "input_contract_ref": agent.input_contract_ref,
        "output_contract_ref": agent.output_contract_ref,
        "criticality": agent.criticality,
        "cost_profile": agent.cost_profile,
        "limitations": agent.limitations,
        "prompt_ref": agent.prompt_ref,
        "prompt_content": agent.prompt_content,
        "skills_ref": agent.skills_ref,
        "skills_content": agent.skills_content,
        "soul_content": agent.soul_content,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "version": agent.version,
        "status": agent.status,
        "owner": agent.owner,
        "last_test_status": agent.last_test_status,
        "last_validated_at": agent.last_validated_at,
        "usage_count": agent.usage_count,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }


async def enrich_agent_skills(db: AsyncSession, agent: AgentDefinition) -> dict:
    """Alias for enrich_agent — returns enriched agent dict with skill_ids and family."""
    return await enrich_agent(db, agent)


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
    if not draft.skill_ids:
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
        family_id=draft.family_id,
        purpose=draft.purpose,
        description=draft.description,
        skill_ids=draft.skill_ids,
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
