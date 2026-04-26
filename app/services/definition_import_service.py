"""Service d'import déclaratif JSON (GH-14)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import AgentSkill
from app.models.registry import AgentDefinition
from app.models.test_lab import TestScenario
from app.services.definition_canonicalization import canonicalize_definition
from app.services.definition_resolver_service import (
    DefinitionValidationError,
    validate_definition_dependencies,
)
from app.services.event_service import emit_event


class DefinitionImportError(ValueError):
    """Erreur bloquante d'import déclaratif."""


@dataclass(slots=True)
class ImportReport:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


def _definition_ref(definition: dict) -> str:
    if definition.get("kind") == "scenario":
        return definition.get("definition_key") or definition.get("name") or "scenario:unknown"
    return definition.get("id") or definition.get("name") or "definition:unknown"


def _sort_key(definition: dict) -> int:
    kind = definition.get("kind")
    if kind == "agent":
        return 0
    if kind == "orchestrator":
        return 1
    if kind == "scenario":
        return 2
    return 99


async def _sync_agent_skills(db: AsyncSession, agent_id: str, skill_ids: list[str]) -> None:
    result = await db.execute(select(AgentSkill).where(AgentSkill.agent_id == agent_id))
    for row in result.scalars().all():
        await db.delete(row)
    await db.flush()

    for sid in skill_ids:
        db.add(AgentSkill(agent_id=agent_id, skill_id=sid))
    await db.flush()


async def _get_agent_skill_ids(db: AsyncSession, agent_id: str) -> list[str]:
    result = await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent_id)
    )
    return [row[0] for row in result.all()]


async def _agent_to_definition(db: AsyncSession, agent: AgentDefinition, kind: str = "agent") -> dict:
    skill_ids = await _get_agent_skill_ids(db, agent.id)
    definition = {
        "kind": kind,
        "schema_version": "v1",
        "id": agent.id,
        "name": agent.name,
        "family_id": agent.family_id,
        "purpose": agent.purpose,
        "description": agent.description,
        "skill_ids": skill_ids,
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
        definition["pipeline_definition"] = agent.pipeline_definition
    return definition


def _scenario_to_definition(scenario: TestScenario) -> dict:
    return {
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


async def _upsert_agent_or_orchestrator(
    db: AsyncSession,
    definition: dict,
    report: ImportReport,
) -> None:
    agent_id = definition["id"]
    kind = definition["kind"]
    existing = await db.get(AgentDefinition, agent_id)

    if existing is None:
        existing = AgentDefinition(id=agent_id)
        db.add(existing)
        action = "created"
    else:
        action = "updated"

    current = None
    if action == "updated":
        current = await _agent_to_definition(db, existing, kind=kind)
        if canonicalize_definition(current) == canonicalize_definition(definition):
            report.skipped += 1
            await emit_event(
                db,
                "definition.import_skipped",
                "system",
                "definition_import",
                payload={"kind": kind, "ref": agent_id},
            )
            return

    existing.name = definition["name"]
    existing.family_id = definition["family_id"]
    existing.purpose = definition["purpose"]
    existing.description = definition.get("description")
    existing.selection_hints = definition.get("selection_hints") or {}
    existing.allowed_mcps = definition.get("allowed_mcps") or []
    existing.forbidden_effects = definition.get("forbidden_effects") or []
    existing.allow_code_execution = definition.get("allow_code_execution", False)
    existing.criticality = definition["criticality"]
    existing.cost_profile = definition["cost_profile"]
    existing.llm_provider = definition.get("llm_provider")
    existing.llm_model = definition.get("llm_model")
    existing.limitations = definition.get("limitations") or []
    existing.prompt_content = definition.get("prompt_content")
    existing.skills_content = definition.get("skills_content")
    existing.version = definition["version"]
    existing.status = definition["status"]

    if kind == "orchestrator":
        pipeline_definition = definition.get("pipeline_definition")
        existing.pipeline_definition = pipeline_definition
        stages = (pipeline_definition or {}).get("stages") or []
        existing.pipeline_agent_ids = [stage.get("agent_id") for stage in stages if stage.get("agent_id")]

    await db.flush()
    await _sync_agent_skills(db, existing.id, definition.get("skill_ids") or [])

    if action == "created":
        report.created += 1
    else:
        report.updated += 1

    await emit_event(
        db,
        "definition.imported",
        "system",
        "definition_import",
        payload={"kind": kind, "ref": existing.id, "action": action},
    )


async def _upsert_scenario(
    db: AsyncSession,
    definition: dict,
    report: ImportReport,
) -> None:
    definition_key = definition["definition_key"]
    existing = (
        await db.execute(
            select(TestScenario).where(TestScenario.definition_key == definition_key)
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = TestScenario(
            definition_key=definition_key,
            name=definition["name"],
            description=definition.get("description"),
            agent_id=definition["agent_id"],
            input_prompt=definition["input_prompt"],
            expected_tools=definition.get("expected_tools") or [],
            assertions=definition.get("assertions") or [],
            timeout_seconds=definition.get("timeout_seconds", 120),
            max_iterations=definition.get("max_iterations", 10),
            tags=definition.get("tags") or [],
            enabled=definition.get("enabled", True),
        )
        db.add(existing)
        await db.flush()
        report.created += 1
        await emit_event(
            db,
            "definition.imported",
            "system",
            "definition_import",
            payload={"kind": "scenario", "ref": definition_key, "action": "created"},
        )
        return

    current = _scenario_to_definition(existing)
    if canonicalize_definition(current) == canonicalize_definition(definition):
        report.skipped += 1
        await emit_event(
            db,
            "definition.import_skipped",
            "system",
            "definition_import",
            payload={"kind": "scenario", "ref": definition_key},
        )
        return

    existing.definition_key = definition_key
    existing.name = definition["name"]
    existing.description = definition.get("description")
    existing.agent_id = definition["agent_id"]
    existing.input_prompt = definition["input_prompt"]
    existing.expected_tools = definition.get("expected_tools") or []
    existing.assertions = definition.get("assertions") or []
    existing.timeout_seconds = definition.get("timeout_seconds", 120)
    existing.max_iterations = definition.get("max_iterations", 10)
    existing.tags = definition.get("tags") or []
    existing.enabled = definition.get("enabled", True)
    await db.flush()
    report.updated += 1

    await emit_event(
        db,
        "definition.imported",
        "system",
        "definition_import",
        payload={"kind": "scenario", "ref": definition_key, "action": "updated"},
    )


def _validate_no_duplicate_keys(definitions: list[dict]) -> None:
    seen_agent_ids: set[str] = set()
    seen_scenario_keys: set[str] = set()

    for definition in definitions:
        kind = definition.get("kind")
        if kind in {"agent", "orchestrator"}:
            ref = definition.get("id")
            if ref in seen_agent_ids:
                raise DefinitionImportError(f"duplicate definition id in payload: {ref}")
            seen_agent_ids.add(ref)
        elif kind == "scenario":
            ref = definition.get("definition_key")
            if ref in seen_scenario_keys:
                raise DefinitionImportError(f"duplicate scenario definition_key in payload: {ref}")
            seen_scenario_keys.add(ref)


async def import_definitions(db: AsyncSession, definitions: list[dict]) -> ImportReport:
    report = ImportReport()
    sorted_definitions = sorted(definitions, key=_sort_key)

    _validate_no_duplicate_keys(sorted_definitions)

    async with db.begin_nested():
        for definition in sorted_definitions:
            try:
                validation = await validate_definition_dependencies(db, definition)
                report.warnings.extend(validation.warnings)

                kind = definition.get("kind")
                if kind in {"agent", "orchestrator"}:
                    await _upsert_agent_or_orchestrator(db, definition, report)
                elif kind == "scenario":
                    await _upsert_scenario(db, definition, report)
                else:
                    raise DefinitionImportError(f"unsupported kind: {kind}")
            except (DefinitionValidationError, DefinitionImportError) as exc:
                report.errors.append(
                    {
                        "ref": _definition_ref(definition),
                        "message": str(exc),
                    }
                )
                raise

    return report
