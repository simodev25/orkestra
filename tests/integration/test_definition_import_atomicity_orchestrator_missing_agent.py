import pytest


@pytest.mark.asyncio
async def test_import_batch_rolls_back_when_orchestrator_stage_agent_missing(client):
    await client.post(
        "/api/families",
        json={"id": "analysis", "label": "Analysis", "description": "Analysis family"},
    )
    await client.post(
        "/api/families",
        json={
            "id": "orchestration",
            "label": "Orchestration",
            "description": "Orchestration family",
        },
    )

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
            },
            {
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
                        {
                            "stage_id": "missing_stage",
                            "agent_id": "does_not_exist",
                            "required": True,
                        }
                    ],
                    "error_policy": "continue_on_partial_failure",
                },
            },
        ]
    }

    response = await client.post("/api/definitions/import", json=payload)
    assert response.status_code == 409
    assert "missing_stage" in response.json()["detail"]

    response_get_weather = await client.get("/api/agents/weather_agent")
    response_get_orchestrator = await client.get("/api/agents/hotel_pipeline_orchestrator")
    assert response_get_weather.status_code == 404
    assert response_get_orchestrator.status_code == 404
