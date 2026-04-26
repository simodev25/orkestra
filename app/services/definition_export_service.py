"""Service d'export déclaratif JSON (GH-14)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import AgentSkill
from app.models.registry import AgentDefinition
from app.models.test_lab import TestScenario
from app.services.event_service import emit_event


class DefinitionExportNotFoundError(ValueError):
    """Levée quand la définition demandée est introuvable."""


async def _agent_skill_ids(db: AsyncSession, agent_id: str) -> list[str]:
    result = await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent_id)
    )
    return [row[0] for row in result.all()]


async def _export_agent_or_orchestrator(
    db: AsyncSession,
    agent: AgentDefinition,
    *,
    kind: str,
) -> dict:
    payload = {
        "kind": kind,
        "schema_version": "v1",
        "id": agent.id,
        "name": agent.name,
        "family_id": agent.family_id,
        "purpose": agent.purpose,
        "description": agent.description,
        "skill_ids": await _agent_skill_ids(db, agent.id),
        "selection_hints": agent.selection_hints or {},
        "allowed_mcps": agent.allowed_mcps or [],
        "forbidden_effects": agent.forbidden_effects or [],
        "allow_code_execution": agent.allow_code_execution,
        "criticality": agent.criticality,
        "cost_profile": agent.cost_profile,
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "limitations": agent.limitations or [],
        "prompt_content": agent.prompt_content,
        "skills_content": agent.skills_content,
        "version": agent.version,
        "status": agent.status,
    }
    if kind == "orchestrator":
        payload["pipeline_definition"] = agent.pipeline_definition

    await emit_event(
        db,
        "definition.export_requested",
        "system",
        "definition_export",
        payload={"kind": kind, "ref": agent.id},
    )
    return payload


async def _export_scenario(db: AsyncSession, scenario: TestScenario) -> dict:
    payload = {
        "kind": "scenario",
        "schema_version": "v1",
        "definition_key": scenario.definition_key,
        "name": scenario.name,
        "description": scenario.description,
        "agent_id": scenario.agent_id,
        "input_prompt": scenario.input_prompt,
        "expected_tools": scenario.expected_tools or [],
        "assertions": scenario.assertions or [],
        "timeout_seconds": scenario.timeout_seconds,
        "max_iterations": scenario.max_iterations,
        "tags": scenario.tags or [],
        "enabled": scenario.enabled,
    }
    await emit_event(
        db,
        "definition.export_requested",
        "system",
        "definition_export",
        payload={"kind": "scenario", "ref": scenario.definition_key},
    )
    return payload


async def export_definition(
    db: AsyncSession,
    *,
    kind: str,
    definition_id: str | None = None,
    definition_key: str | None = None,
) -> dict:
    if kind == "agent":
        if not definition_id:
            raise ValueError("id is required for kind=agent")
        agent = await db.get(AgentDefinition, definition_id)
        if not agent:
            raise DefinitionExportNotFoundError(f"agent '{definition_id}' not found")
        return await _export_agent_or_orchestrator(db, agent, kind="agent")

    if kind == "orchestrator":
        if not definition_id:
            raise ValueError("id is required for kind=orchestrator")
        agent = await db.get(AgentDefinition, definition_id)
        if not agent:
            raise DefinitionExportNotFoundError(f"orchestrator '{definition_id}' not found")
        return await _export_agent_or_orchestrator(db, agent, kind="orchestrator")

    if kind == "scenario":
        if not definition_key:
            raise ValueError("definition_key is required for kind=scenario")
        scenario = (
            await db.execute(
                select(TestScenario).where(TestScenario.definition_key == definition_key)
            )
        ).scalar_one_or_none()
        if not scenario:
            raise DefinitionExportNotFoundError(
                f"scenario '{definition_key}' not found"
            )
        return await _export_scenario(db, scenario)

    raise ValueError(f"Unsupported kind '{kind}'")
