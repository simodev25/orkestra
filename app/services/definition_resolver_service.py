"""Validation des dépendances pour définitions déclaratives GH-14."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import FamilyDefinition
from app.models.registry import AgentDefinition
from app.services import obot_catalog_service, skill_service


class DefinitionValidationError(ValueError):
    """Erreur bloquante de validation de dépendances."""


@dataclass(slots=True)
class DefinitionValidationResult:
    warnings: list[dict] = field(default_factory=list)


def _definition_ref(definition: dict) -> str:
    if definition.get("kind") == "scenario":
        return definition.get("definition_key") or definition.get("name") or "scenario:unknown"
    return definition.get("id") or definition.get("name") or "definition:unknown"


async def _validate_family(db: AsyncSession, definition: dict) -> None:
    family_id = definition.get("family_id")
    family = await db.get(FamilyDefinition, family_id)
    if not family:
        raise DefinitionValidationError(
            f"Validation error for ref='{_definition_ref(definition)}': family_id '{family_id}' not found"
        )
    if family.status != "active":
        raise DefinitionValidationError(
            f"Validation error for ref='{_definition_ref(definition)}': family_id '{family_id}' not active"
        )


async def _validate_skills(db: AsyncSession, definition: dict) -> None:
    skill_ids = definition.get("skill_ids") or []
    if not skill_ids:
        return

    _, unresolved = await skill_service.resolve_skills(db, skill_ids)
    if unresolved:
        raise DefinitionValidationError(
            f"Validation error for ref='{_definition_ref(definition)}': unknown skill_ids {unresolved}"
        )

    incompatible = await skill_service.validate_skills_for_family(
        db,
        skill_ids,
        definition["family_id"],
    )
    if incompatible:
        raise DefinitionValidationError(
            f"Validation error for ref='{_definition_ref(definition)}': skills not allowed for family_id '{definition['family_id']}': {incompatible}"
        )


async def _validate_allowed_mcps(db: AsyncSession, definition: dict) -> list[dict]:
    allowed_mcps = definition.get("allowed_mcps") or []
    if not allowed_mcps:
        return []

    items, _ = await obot_catalog_service.list_catalog_items(db, limit=100000)
    catalog_ids = {item.obot_server.id for item in items}
    unresolved = [mcp_id for mcp_id in allowed_mcps if mcp_id not in catalog_ids]
    if not unresolved:
        return []

    return [
        {
            "ref": _definition_ref(definition),
            "code": "allowed_mcps.unresolved",
            "message": f"Unknown MCP ids in allowed_mcps: {unresolved}",
            "field": "allowed_mcps",
        }
    ]


async def _validate_scenario_agent_ref(db: AsyncSession, definition: dict) -> None:
    agent_id = definition.get("agent_id")
    agent = await db.get(AgentDefinition, agent_id)
    if not agent:
        raise DefinitionValidationError(
            f"Validation error for ref='{_definition_ref(definition)}': agent_id '{agent_id}' not found"
        )


async def _validate_orchestrator_pipeline_agents(db: AsyncSession, definition: dict) -> None:
    pipeline = definition.get("pipeline_definition") or {}
    stages = pipeline.get("stages") or []
    for stage in stages:
        agent_id = stage.get("agent_id")
        stage_id = stage.get("stage_id")
        agent = await db.get(AgentDefinition, agent_id)
        if not agent:
            raise DefinitionValidationError(
                f"Validation error for ref='{_definition_ref(definition)}': pipeline_definition.stages[{stage_id}].agent_id '{agent_id}' not found"
            )


async def validate_definition_dependencies(
    db: AsyncSession,
    definition: dict,
) -> DefinitionValidationResult:
    kind = definition.get("kind")
    warnings: list[dict] = []

    if kind in {"agent", "orchestrator"}:
        await _validate_family(db, definition)
        await _validate_skills(db, definition)
        warnings.extend(await _validate_allowed_mcps(db, definition))

    if kind == "scenario":
        await _validate_scenario_agent_ref(db, definition)

    if kind == "orchestrator":
        await _validate_orchestrator_pipeline_agents(db, definition)

    return DefinitionValidationResult(warnings=warnings)


async def validate_definitions_batch(
    db: AsyncSession,
    definitions: list[dict],
) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    warnings: list[dict] = []

    for definition in definitions:
        try:
            result = await validate_definition_dependencies(db, definition)
            warnings.extend(result.warnings)
        except DefinitionValidationError as exc:
            errors.append(
                {
                    "ref": _definition_ref(definition),
                    "code": "dependency_validation_error",
                    "message": str(exc),
                }
            )

    return errors, warnings
