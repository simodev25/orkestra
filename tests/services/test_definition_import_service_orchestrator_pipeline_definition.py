import pytest


@pytest.mark.asyncio
async def test_import_orchestrator_persists_pipeline_definition_and_legacy_ids(db_session):
    from app.models.family import FamilyDefinition
    from app.models.registry import AgentDefinition
    from app.services.definition_import_service import import_definitions

    db_session.add(FamilyDefinition(id="analysis", label="Analysis", status="active"))
    db_session.add(FamilyDefinition(id="orchestration", label="Orchestration", status="active"))
    db_session.add(
        AgentDefinition(
            id="stay_discovery_agent",
            name="Stay Discovery",
            family_id="analysis",
            purpose="Discover stays",
            criticality="low",
            cost_profile="low",
            version="1.0.0",
            status="draft",
        )
    )
    db_session.add(
        AgentDefinition(
            id="weather_agent",
            name="Weather Agent",
            family_id="analysis",
            purpose="Weather context",
            criticality="low",
            cost_profile="low",
            version="1.0.0",
            status="draft",
        )
    )
    await db_session.commit()

    definition = {
        "kind": "orchestrator",
        "schema_version": "v1",
        "id": "hotel_pipeline_orchestrator",
        "name": "Hotel Pipeline Orchestrator",
        "family_id": "orchestration",
        "purpose": "Orchestrer les agents du pipeline hôtelier.",
        "description": "Pipeline séquentiel.",
        "skill_ids": [],
        "selection_hints": {},
        "allowed_mcps": [],
        "forbidden_effects": [],
        "allow_code_execution": False,
        "criticality": "medium",
        "cost_profile": "medium",
        "llm_provider": "ollama",
        "llm_model": "mistral",
        "limitations": [],
        "prompt_content": "Prompt",
        "skills_content": None,
        "version": "1.0.0",
        "status": "draft",
        "pipeline_definition": {
            "routing_mode": "sequential",
            "stages": [
                {"stage_id": "stay", "agent_id": "stay_discovery_agent", "required": True},
                {"stage_id": "weather", "agent_id": "weather_agent", "required": True},
            ],
            "error_policy": "continue_on_partial_failure",
        },
    }

    report = await import_definitions(db_session, [definition])
    assert report.created == 1

    orchestrator = await db_session.get(AgentDefinition, "hotel_pipeline_orchestrator")
    assert orchestrator is not None
    assert orchestrator.pipeline_definition == definition["pipeline_definition"]
    assert orchestrator.pipeline_agent_ids == ["stay_discovery_agent", "weather_agent"]
