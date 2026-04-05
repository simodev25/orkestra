"""Family service — CRUD with business guards."""

from __future__ import annotations

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import FamilyDefinition, SkillFamily, AgentSkill
from app.models.registry import AgentDefinition
from app.models.skill import SkillDefinition
from app.schemas.family import FamilyCreate, FamilyUpdate

logger = logging.getLogger("orkestra.families")


async def list_families(db: AsyncSession, *, include_archived: bool = False) -> list[FamilyDefinition]:
    stmt = select(FamilyDefinition).order_by(FamilyDefinition.label)
    if not include_archived:
        stmt = stmt.where(FamilyDefinition.status != "archived")
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_family(db: AsyncSession, family_id: str) -> FamilyDefinition | None:
    return await db.get(FamilyDefinition, family_id)


async def get_family_detail(db: AsyncSession, family_id: str) -> dict | None:
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        return None

    result = await db.execute(
        select(SkillDefinition)
        .join(SkillFamily, SkillFamily.skill_id == SkillDefinition.id)
        .where(SkillFamily.family_id == family_id)
        .order_by(SkillDefinition.label)
    )
    skills = list(result.scalars().all())

    agent_count_result = await db.execute(
        select(func.count()).select_from(AgentDefinition).where(AgentDefinition.family_id == family_id)
    )
    agent_count = agent_count_result.scalar() or 0

    return {
        "id": family.id,
        "label": family.label,
        "description": family.description,
        "default_system_rules": family.default_system_rules or [],
        "default_forbidden_effects": family.default_forbidden_effects or [],
        "default_output_expectations": family.default_output_expectations or [],
        "version": family.version,
        "status": family.status,
        "owner": family.owner,
        "created_at": family.created_at,
        "updated_at": family.updated_at,
        "skills": [{"skill_id": s.id, "label": s.label, "category": s.category} for s in skills],
        "agent_count": agent_count,
    }


async def create_family(db: AsyncSession, data: FamilyCreate) -> FamilyDefinition:
    existing = await db.get(FamilyDefinition, data.id)
    if existing:
        raise ValueError(f"Family '{data.id}' already exists")

    family = FamilyDefinition(
        id=data.id,
        label=data.label,
        description=data.description,
        default_system_rules=data.default_system_rules,
        default_forbidden_effects=data.default_forbidden_effects,
        default_output_expectations=data.default_output_expectations,
        version=data.version,
        status=data.status,
        owner=data.owner,
    )
    db.add(family)
    await db.flush()
    return family


async def update_family(db: AsyncSession, family_id: str, data: FamilyUpdate) -> FamilyDefinition:
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise ValueError(f"Family '{family_id}' not found")

    updates = data.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(family, field, value)

    await db.flush()
    return family


async def archive_family(db: AsyncSession, family_id: str) -> FamilyDefinition:
    """Always set the family status to 'archived'."""
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise ValueError(f"Family '{family_id}' not found")
    family.status = "archived"
    await db.flush()
    return family


async def is_family_active(db: AsyncSession, family_id: str) -> bool:
    """Return True if the family exists and has status 'active'."""
    family = await db.get(FamilyDefinition, family_id)
    return family is not None and family.status == "active"


async def delete_family(db: AsyncSession, family_id: str) -> FamilyDefinition | None:
    """Delete the family if unreferenced; archive it if referenced by agents or skills.

    Returns the updated FamilyDefinition when archived, None when hard-deleted.
    """
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise ValueError(f"Family '{family_id}' not found")

    agent_result = await db.execute(
        select(AgentDefinition.id)
        .where(AgentDefinition.family_id == family_id)
        .limit(1)
    )
    has_agents = agent_result.scalar_one_or_none() is not None

    sf_result = await db.execute(
        select(SkillFamily.skill_id).where(SkillFamily.family_id == family_id).limit(1)
    )
    has_skills = sf_result.scalar_one_or_none() is not None

    if has_agents or has_skills:
        family.status = "archived"
        await db.flush()
        return family

    await db.delete(family)
    await db.flush()
    return None
