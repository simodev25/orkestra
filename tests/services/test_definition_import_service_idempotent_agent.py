import pytest


@pytest.mark.asyncio
async def test_import_agent_idempotent_second_import_is_skip(db_session):
    from app.models.family import FamilyDefinition
    from app.services.definition_import_service import import_definitions

    db_session.add(FamilyDefinition(id="analysis", label="Analysis", status="active"))
    await db_session.commit()

    payload = {
        "definitions": [
            {
                "kind": "agent",
                "schema_version": "v1",
                "id": "weather_agent",
                "name": "Weather Agent",
                "family_id": "analysis",
                "purpose": "Fournir un contexte météo.",
                "description": "Desc",
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
        ]
    }

    first = await import_definitions(db_session, payload["definitions"])
    second = await import_definitions(db_session, payload["definitions"])

    assert first.created == 1
    assert first.updated == 0
    assert first.skipped == 0

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1
