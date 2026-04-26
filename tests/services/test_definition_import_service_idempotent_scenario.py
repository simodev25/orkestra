import pytest


@pytest.mark.asyncio
async def test_import_scenario_idempotent_by_definition_key(db_session):
    from app.models.family import FamilyDefinition
    from app.models.registry import AgentDefinition
    from app.services.definition_import_service import import_definitions

    db_session.add(FamilyDefinition(id="analysis", label="Analysis", status="active"))
    db_session.add(
        AgentDefinition(
            id="weather_agent",
            name="Weather Agent",
            family_id="analysis",
            purpose="Weather purpose",
            criticality="low",
            cost_profile="low",
            version="1.0.0",
            status="draft",
        )
    )
    await db_session.commit()

    definitions = [
        {
            "kind": "scenario",
            "schema_version": "v1",
            "definition_key": "weather_context_lisbon_may_2026",
            "name": "Weather Lisbon",
            "description": "Scenario météo",
            "agent_id": "weather_agent",
            "input_prompt": "Quel temps à Lisbonne ?",
            "expected_tools": [],
            "assertions": [{"type": "output_contains", "target": "forecast", "critical": True}],
            "timeout_seconds": 120,
            "max_iterations": 10,
            "tags": ["weather"],
            "enabled": True,
        }
    ]

    first = await import_definitions(db_session, definitions)
    second = await import_definitions(db_session, definitions)

    assert first.created == 1
    assert first.updated == 0
    assert first.skipped == 0

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1
