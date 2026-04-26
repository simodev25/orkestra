import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_definitions_endpoints_and_events_flow(client):
    await client.post(
        "/api/families",
        json={"id": "analysis", "label": "Analysis", "description": "Analysis family"},
    )

    definition = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "weather_agent",
        "name": "Weather Agent",
        "family_id": "analysis",
        "purpose": "Fournir un contexte météo.",
        "description": "Desc",
        "skill_ids": [],
        "selection_hints": {},
        "allowed_mcps": ["unknown_mcp_id"],
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

    validate_response = await client.post("/api/definitions/validate", json={"definitions": [definition]})
    assert validate_response.status_code == 200
    body = validate_response.json()
    assert body["valid"] is True
    assert len(body["warnings"]) == 1
    assert body["warnings"][0]["code"] == "allowed_mcps.unresolved"

    first_import = await client.post("/api/definitions/import", json={"definitions": [definition]})
    assert first_import.status_code == 200
    assert first_import.json()["created"] == 1

    second_import = await client.post("/api/definitions/import", json={"definitions": [definition]})
    assert second_import.status_code == 200
    assert second_import.json()["skipped"] == 1

    export_response = await client.get("/api/definitions/export", params={"kind": "agent", "id": "weather_agent"})
    assert export_response.status_code == 200
    assert export_response.json()["id"] == "weather_agent"

    from tests.conftest import test_session_factory
    from app.models.audit import AuditEvent

    async with test_session_factory() as db:
        events = (
            await db.execute(
                select(AuditEvent.event_type).where(
                    AuditEvent.event_type.in_(
                        [
                            "definition.imported",
                            "definition.import_skipped",
                            "definition.export_requested",
                        ]
                    )
                )
            )
        ).all()
        emitted = {row[0] for row in events}

    assert "definition.imported" in emitted
    assert "definition.import_skipped" in emitted
    assert "definition.export_requested" in emitted
