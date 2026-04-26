import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_import_scenario_upsert_same_definition_key_updates_existing(db_session):
    from app.models.family import FamilyDefinition
    from app.models.registry import AgentDefinition
    from app.models.test_lab import TestScenario
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

    original = TestScenario(
        definition_key="weather_context_lisbon_may_2026",
        name="Weather Lisbon",
        description="Desc V1",
        agent_id="weather_agent",
        input_prompt="Prompt V1",
        expected_tools=[],
        assertions=[],
        timeout_seconds=120,
        max_iterations=10,
        tags=["weather"],
        enabled=True,
    )
    db_session.add(original)
    await db_session.commit()

    definition = {
        "kind": "scenario",
        "schema_version": "v1",
        "definition_key": "weather_context_lisbon_may_2026",
        "name": "Weather Lisbon",
        "description": "Desc V2",
        "agent_id": "weather_agent",
        "input_prompt": "Prompt V2",
        "expected_tools": [],
        "assertions": [{"type": "output_contains", "target": "forecast", "critical": True}],
        "timeout_seconds": 120,
        "max_iterations": 10,
        "tags": ["weather"],
        "enabled": True,
    }

    report = await import_definitions(db_session, [definition])
    assert report.updated == 1
    assert report.created == 0

    scenarios = (
        await db_session.execute(
            select(TestScenario).where(
                TestScenario.definition_key == "weather_context_lisbon_may_2026"
            )
        )
    ).scalars().all()

    assert len(scenarios) == 1
    assert scenarios[0].description == "Desc V2"
    assert scenarios[0].input_prompt == "Prompt V2"
