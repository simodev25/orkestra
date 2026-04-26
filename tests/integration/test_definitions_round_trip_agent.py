import pytest


@pytest.mark.asyncio
async def test_round_trip_agent_import_export_reimport(client):
    await client.post(
        "/api/families",
        json={"id": "analysis", "label": "Analysis", "description": "Analysis family"},
    )

    source = {
        "kind": "agent",
        "schema_version": "v1",
        "id": "budget_fit_agent",
        "name": "Budget Fit Agent",
        "family_id": "analysis",
        "purpose": "Scoring budget fit",
        "description": "Deterministic scoring",
        "skill_ids": [],
        "selection_hints": {"workflow_ids": ["hotel_pipeline"]},
        "allowed_mcps": [],
        "forbidden_effects": ["write"],
        "allow_code_execution": False,
        "criticality": "medium",
        "cost_profile": "low",
        "llm_provider": "ollama",
        "llm_model": "mistral",
        "limitations": ["No external calls"],
        "prompt_content": "Prompt",
        "skills_content": None,
        "version": "1.0.0",
        "status": "draft",
    }

    first_import = await client.post("/api/definitions/import", json={"definitions": [source]})
    assert first_import.status_code == 200
    assert first_import.json()["created"] == 1

    exported = await client.get("/api/definitions/export", params={"kind": "agent", "id": "budget_fit_agent"})
    assert exported.status_code == 200
    payload = exported.json()

    reimport = await client.post("/api/definitions/import", json={"definitions": [payload]})
    assert reimport.status_code == 200
    assert reimport.json()["skipped"] == 1

    second_export = await client.get("/api/definitions/export", params={"kind": "agent", "id": "budget_fit_agent"})
    assert second_export.status_code == 200

    for field in [
        "kind",
        "schema_version",
        "id",
        "name",
        "family_id",
        "purpose",
        "description",
        "skill_ids",
        "selection_hints",
        "allowed_mcps",
        "forbidden_effects",
        "allow_code_execution",
        "criticality",
        "cost_profile",
        "llm_provider",
        "llm_model",
        "limitations",
        "prompt_content",
        "skills_content",
        "version",
        "status",
    ]:
        assert second_export.json()[field] == source[field]
