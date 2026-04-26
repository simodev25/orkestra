import pytest


@pytest.mark.asyncio
async def test_import_agent_update_without_version_bump(db_session):
    from app.models.family import FamilyDefinition
    from app.services.definition_import_service import import_definitions

    db_session.add(FamilyDefinition(id="analysis", label="Analysis", status="active"))
    await db_session.commit()

    base_definition = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "analysis",
        "purpose": "Fournir un contexte météo.",
        "description": "Desc V1",
        "skill_ids": [],
        "selection_hints": {},
        "allowed_mcps": [],
        "forbidden_effects": [],
        "allow_code_execution": False,
        "criticality": "low",
        "cost_profile": "low",
        "llm_provider": "ollama",
        "llm_model": "mistral",
        "limitations": [],
        "prompt_content": "Prompt",
        "skills_content": None,
        "version": "1.0.0",
        "status": "draft",
    }

    updated_definition = {
        **base_definition,
        "description": "Desc V2",
    }

    first = await import_definitions(db_session, [base_definition])
    second = await import_definitions(db_session, [updated_definition])

    assert first.created == 1
    assert second.updated == 1
    assert second.skipped == 0

    from app.models.registry import AgentDefinition

    agent = await db_session.get(AgentDefinition, "weather_agent")
    assert agent is not None
    assert agent.description == "Desc V2"
    assert agent.version == "1.0.0"
