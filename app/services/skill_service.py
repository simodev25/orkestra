"""Skill service — DB-backed CRUD, replaces skill_registry_service."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import SkillFamily, AgentSkill
from app.models.registry import AgentDefinition
from app.models.skill import SkillDefinition
from app.schemas.skill import SkillContent, SkillCreate, SkillRef, SkillUpdate

logger = logging.getLogger("orkestra.skills")


async def list_skills(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SkillDefinition).order_by(SkillDefinition.label))
    skills = list(result.scalars().all())
    out = []
    for s in skills:
        families = await _get_allowed_families(db, s.id)
        out.append(_skill_to_dict(s, families))
    return out


async def get_skill(db: AsyncSession, skill_id: str) -> dict | None:
    skill = await db.get(SkillDefinition, skill_id)
    if not skill:
        return None
    families = await _get_allowed_families(db, skill_id)
    return _skill_to_dict(skill, families)


async def get_skills_for_family(db: AsyncSession, family_id: str) -> list[dict]:
    result = await db.execute(
        select(SkillDefinition)
        .join(SkillFamily, SkillFamily.skill_id == SkillDefinition.id)
        .where(SkillFamily.family_id == family_id)
        .order_by(SkillDefinition.label)
    )
    skills = list(result.scalars().all())
    out = []
    for s in skills:
        families = await _get_allowed_families(db, s.id)
        out.append(_skill_to_dict(s, families))
    return out


async def create_skill(db: AsyncSession, data: SkillCreate) -> dict:
    existing = await db.get(SkillDefinition, data.id)
    if existing:
        raise ValueError(f"Skill '{data.id}' already exists")

    await _validate_family_ids(db, data.allowed_families)

    skill = SkillDefinition(
        id=data.id,
        label=data.label,
        category=data.category,
        description=data.description,
        behavior_templates=data.behavior_templates,
        output_guidelines=data.output_guidelines,
    )
    db.add(skill)
    await db.flush()

    for fam_id in data.allowed_families:
        db.add(SkillFamily(skill_id=data.id, family_id=fam_id))
    await db.flush()

    return _skill_to_dict(skill, data.allowed_families)


async def update_skill(db: AsyncSession, skill_id: str, data: SkillUpdate) -> dict:
    skill = await db.get(SkillDefinition, skill_id)
    if not skill:
        raise ValueError(f"Skill '{skill_id}' not found")

    updates = data.model_dump(exclude_none=True)
    new_families = updates.pop("allowed_families", None)

    for field, value in updates.items():
        setattr(skill, field, value)

    if new_families is not None:
        await _validate_family_ids(db, new_families)

        current_families = set(await _get_allowed_families(db, skill_id))
        removed_families = current_families - set(new_families)
        if removed_families:
            for fam_id in removed_families:
                result = await db.execute(
                    select(AgentDefinition.id, AgentDefinition.name)
                    .join(AgentSkill, AgentSkill.agent_id == AgentDefinition.id)
                    .where(AgentSkill.skill_id == skill_id, AgentDefinition.family_id == fam_id)
                    .limit(5)
                )
                conflicting = result.all()
                if conflicting:
                    names = ", ".join(f"{a.name} ({a.id})" for a in conflicting)
                    raise ValueError(
                        f"Cannot remove family '{fam_id}' from skill '{skill_id}': "
                        f"used by agents in that family: {names}"
                    )

        await db.execute(delete(SkillFamily).where(SkillFamily.skill_id == skill_id))
        for fam_id in new_families:
            db.add(SkillFamily(skill_id=skill_id, family_id=fam_id))

    await db.flush()

    await _cascade_skills_content(db, skill_id)

    families = await _get_allowed_families(db, skill_id)
    return _skill_to_dict(skill, families)


async def delete_skill(db: AsyncSession, skill_id: str) -> None:
    skill = await db.get(SkillDefinition, skill_id)
    if not skill:
        raise ValueError(f"Skill '{skill_id}' not found")

    result = await db.execute(
        select(AgentDefinition.id, AgentDefinition.name)
        .join(AgentSkill, AgentSkill.agent_id == AgentDefinition.id)
        .where(AgentSkill.skill_id == skill_id)
        .limit(10)
    )
    agents = result.all()
    if agents:
        names = ", ".join(f"{a.name} ({a.id})" for a in agents)
        raise ValueError(f"Cannot delete skill '{skill_id}': used by agents: {names}")

    await db.delete(skill)
    await db.flush()


async def resolve_skills(db: AsyncSession, skill_ids: list[str]) -> tuple[list[SkillRef], list[str]]:
    resolved: list[SkillRef] = []
    unresolved: list[str] = []
    for sid in skill_ids:
        skill = await db.get(SkillDefinition, sid)
        if not skill:
            unresolved.append(sid)
            continue
        resolved.append(SkillRef(
            skill_id=skill.id,
            label=skill.label,
            category=skill.category,
            skills_content=SkillContent(
                description=skill.description or "",
                behavior_templates=skill.behavior_templates or [],
                output_guidelines=skill.output_guidelines or [],
            ),
        ))
    return resolved, unresolved


async def build_skills_content(db: AsyncSession, skill_ids: list[str]) -> str:
    resolved, _ = await resolve_skills(db, skill_ids)
    content = {
        ref.skill_id: {
            "description": ref.skills_content.description,
            "behavior_templates": ref.skills_content.behavior_templates,
            "output_guidelines": ref.skills_content.output_guidelines,
        }
        for ref in resolved
    }
    return json.dumps(content, indent=2)


async def validate_skills_for_family(
    db: AsyncSession, skill_ids: list[str], family_id: str
) -> list[str]:
    incompatible = []
    for sid in skill_ids:
        result = await db.execute(
            select(SkillFamily).where(
                SkillFamily.skill_id == sid,
                SkillFamily.family_id == family_id,
            )
        )
        if not result.scalar_one_or_none():
            incompatible.append(sid)
    return incompatible


async def _get_allowed_families(db: AsyncSession, skill_id: str) -> list[str]:
    result = await db.execute(
        select(SkillFamily.family_id).where(SkillFamily.skill_id == skill_id)
    )
    return [row[0] for row in result.all()]


async def _validate_family_ids(db: AsyncSession, family_ids: list[str]) -> None:
    from app.models.family import FamilyDefinition
    for fid in family_ids:
        if not await db.get(FamilyDefinition, fid):
            raise ValueError(f"Family '{fid}' not found")


async def _cascade_skills_content(db: AsyncSession, skill_id: str) -> None:
    result = await db.execute(
        select(AgentDefinition)
        .join(AgentSkill, AgentSkill.agent_id == AgentDefinition.id)
        .where(AgentSkill.skill_id == skill_id)
    )
    agents = list(result.scalars().all())
    for agent in agents:
        sk_result = await db.execute(
            select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent.id)
        )
        all_skill_ids = [row[0] for row in sk_result.all()]
        agent.skills_content = await build_skills_content(db, all_skill_ids)
    await db.flush()


def _skill_to_dict(skill: SkillDefinition, families: list[str]) -> dict:
    return {
        "skill_id": skill.id,
        "label": skill.label,
        "category": skill.category,
        "description": skill.description,
        "behavior_templates": skill.behavior_templates or [],
        "output_guidelines": skill.output_guidelines or [],
        "allowed_families": families,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }
