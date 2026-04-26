import pytest


@pytest.mark.asyncio
async def test_validate_family_id_unknown_fails(db_session):
    from app.services.definition_resolver_service import (
        DefinitionValidationError,
        validate_definition_dependencies,
    )

    payload = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "unknown_family",
        "purpose": "Fournir un contexte météo.",
        "criticality": "low",
        "cost_profile": "low",
        "version": "1.0.0",
        "status": "draft",
    }

    with pytest.raises(DefinitionValidationError, match="family_id"):
        await validate_definition_dependencies(db_session, payload)


@pytest.mark.asyncio
async def test_validate_family_id_inactive_fails(db_session):
    from app.models.family import FamilyDefinition
    from app.services.definition_resolver_service import (
        DefinitionValidationError,
        validate_definition_dependencies,
    )

    db_session.add(
        FamilyDefinition(
            id="analysis",
            label="Analysis",
            status="archived",
        )
    )
    await db_session.commit()

    payload = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "analysis",
        "purpose": "Fournir un contexte météo.",
        "criticality": "low",
        "cost_profile": "low",
        "version": "1.0.0",
        "status": "draft",
    }

    with pytest.raises(DefinitionValidationError, match="not active"):
        await validate_definition_dependencies(db_session, payload)
