"""Skills API routes — DB-backed CRUD for skill definitions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.skill import (
    AgentSummary,
    SkillCreate,
    SkillOut,
    SkillUpdate,
    SkillWithAgents,
)
from app.services import skill_service

router = APIRouter()


@router.get("/by-family/{family_id}", response_model=list[SkillOut])
async def list_skills_by_family(
    family_id: str,
    include_archived: bool = Query(False, alias="include_archived"),
    db: AsyncSession = Depends(get_db),
):
    return await skill_service.get_skills_for_family(db, family_id, include_archived=include_archived)


@router.get("/with-agents", response_model=list[SkillWithAgents])
async def list_skills_with_agents(db: AsyncSession = Depends(get_db)):
    from app.models.family import AgentSkill
    from app.models.registry import AgentDefinition
    from sqlalchemy import select

    all_skills = await skill_service.list_skills(db)

    skill_agent_map: dict[str, list[AgentSummary]] = {s["skill_id"]: [] for s in all_skills}

    result = await db.execute(
        select(AgentSkill.skill_id, AgentDefinition.id, AgentDefinition.name)
        .join(AgentDefinition, AgentSkill.agent_id == AgentDefinition.id)
    )
    for skill_id, agent_id, agent_name in result.all():
        if skill_id in skill_agent_map:
            skill_agent_map[skill_id].append(AgentSummary(agent_id=agent_id, label=agent_name))

    return [
        SkillWithAgents(
            skill_id=s["skill_id"],
            label=s["label"],
            category=s["category"],
            description=s.get("description"),
            behavior_templates=s.get("behavior_templates", []),
            output_guidelines=s.get("output_guidelines", []),
            allowed_families=s.get("allowed_families", []),
            version=s.get("version"),
            status=s.get("status"),
            owner=s.get("owner"),
            agents=skill_agent_map.get(s["skill_id"], []),
        )
        for s in all_skills
    ]


@router.get("", response_model=list[SkillOut])
async def list_skills(
    include_archived: bool = Query(False, alias="include_archived"),
    db: AsyncSession = Depends(get_db),
):
    return await skill_service.list_skills(db, include_archived=include_archived)


@router.get("/{skill_id}/history")
async def get_skill_history(skill_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.skill_service import get_skill_history as get_history
    history = await get_history(db, skill_id)
    return [
        {
            "id": h.id,
            "skill_id": h.skill_id,
            "label": h.label,
            "category": h.category,
            "description": h.description,
            "behavior_templates": h.behavior_templates,
            "output_guidelines": h.output_guidelines,
            "version": h.version,
            "status": h.status,
            "owner": h.owner,
            "allowed_families_snapshot": h.allowed_families_snapshot,
            "replaced_at": h.replaced_at.isoformat(),
        }
        for h in history
    ]


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    skill = await skill_service.get_skill(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return skill


@router.post("", response_model=SkillOut, status_code=201)
async def create_skill(data: SkillCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await skill_service.create_skill(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{skill_id}/archive", response_model=SkillOut)
async def archive_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await skill_service.archive_skill(db, skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{skill_id}", response_model=SkillOut)
async def update_skill(skill_id: str, data: SkillUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await skill_service.update_skill(db, skill_id, data)
    except ValueError as exc:
        if "Cannot remove" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{skill_id}", response_model=SkillOut | None)
async def delete_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    """Delete (if unreferenced) or archive (if referenced by agents) the skill.

    Returns 200 with archived skill body when references exist, 204 when hard-deleted.
    """
    try:
        result = await skill_service.delete_skill(db, skill_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if result is not None:
        # Was archived — return 200 with the skill body
        return result
    return Response(status_code=status.HTTP_204_NO_CONTENT)
