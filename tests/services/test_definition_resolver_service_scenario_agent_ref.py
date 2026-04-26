import pytest


@pytest.mark.asyncio
async def test_validate_scenario_unknown_agent_fails(db_session):
    from app.services.definition_resolver_service import (
        DefinitionValidationError,
        validate_definition_dependencies,
    )

    payload = {
        "kind": "scenario",
        "schema_version": "v1",
        "definition_key": "weather_context_lisbon_may_2026",
        "name": "Weather Lisbon",
        "description": "Scenario météo",
        "agent_id": "missing_agent",
        "input_prompt": "Quel temps à Lisbonne ?",
        "expected_tools": [],
        "assertions": [],
        "timeout_seconds": 120,
        "max_iterations": 10,
        "tags": [],
        "enabled": True,
    }

    with pytest.raises(DefinitionValidationError, match="agent_id"):
        await validate_definition_dependencies(db_session, payload)
