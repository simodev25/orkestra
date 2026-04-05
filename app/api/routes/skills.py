"""Skills API routes — expose skill registry to the Agent Skills UI page."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.skill import AgentSummary, SkillOut, SkillWithAgents
from app.services import agent_registry_service, skill_registry_service

router = APIRouter()


@router.get("", response_model=list[SkillOut])
async def list_skills():
    """Return all registered skills from the seed (no agent info)."""
    return skill_registry_service.list_skills()


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(skill_id: str):
    """Return a single skill by skill_id."""
    skill = skill_registry_service.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return skill


@router.get("/with-agents", response_model=list[SkillWithAgents])
async def list_skills_with_agents(db: AsyncSession = Depends(get_db)):
    """Return all skills enriched with the agents that reference each skill.

    This is the primary endpoint used by the Agent Skills UI page.
    It aggregates data from:
    - The skill seed (skills.seed.json) — skill metadata
    - The agent registry — which agents declare which skill_ids
    """
    agents = await agent_registry_service.list_agents(db, limit=10000, offset=0)

    # Build skill_id -> list of AgentSummary
    skill_agent_map: dict[str, list[AgentSummary]] = {
        sid: [] for sid in skill_registry_service.get_registry()
    }

    for agent in agents:
        if not agent.skills:
            continue
        for skill_id in agent.skills:
            if skill_id in skill_agent_map:
                skill_agent_map[skill_id].append(
                    AgentSummary(agent_id=agent.id, label=agent.name)
                )

    # Build result
    all_skills = skill_registry_service.list_skills()
    result: list[SkillWithAgents] = []
    for skill in all_skills:
        result.append(
            SkillWithAgents(
                skill_id=skill.skill_id,
                label=skill.label,
                category=skill.category,
                description=skill.description,
                agents=skill_agent_map.get(skill.skill_id, []),
            )
        )
    return result
