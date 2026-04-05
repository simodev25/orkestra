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


async def list_families(db: AsyncSession) -> list[FamilyDefinition]:
    result = await db.execute(
        select(FamilyDefinition).order_by(FamilyDefinition.label)
    )
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
        "created_at": family.created_at,
        "updated_at": family.updated_at,
        "skills": [{"skill_id": s.id, "label": s.label, "category": s.category} for s in skills],
        "agent_count": agent_count,
    }


async def create_family(db: AsyncSession, data: FamilyCreate) -> FamilyDefinition:
    existing = await db.get(FamilyDefinition, data.id)
    if existing:
        raise ValueError(f"Family '{data.id}' already exists")

    family = FamilyDefinition(id=data.id, label=data.label, description=data.description)
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


async def delete_family(db: AsyncSession, family_id: str) -> None:
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise ValueError(f"Family '{family_id}' not found")

    agent_result = await db.execute(
        select(AgentDefinition.id, AgentDefinition.name)
        .where(AgentDefinition.family_id == family_id)
        .limit(10)
    )
    agents = agent_result.all()
    if agents:
        names = ", ".join(f"{a.name} ({a.id})" for a in agents)
        raise ValueError(f"Cannot delete family '{family_id}': used by agents: {names}")

    sf_result = await db.execute(
        select(SkillFamily.skill_id).where(SkillFamily.family_id == family_id).limit(10)
    )
    skill_ids = [row[0] for row in sf_result.all()]
    if skill_ids:
        raise ValueError(
            f"Cannot delete family '{family_id}': referenced by skills: {', '.join(skill_ids)}"
        )

    await db.delete(family)
    await db.flush()
