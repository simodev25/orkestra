import pytest


@pytest.mark.asyncio
async def test_import_definitions_invalid_schema_returns_422(client):
    payload = {
        "definitions": [
            {
                "kind": "agent",
                "schema_version": "v2",
                "id": "weather_agent",
            }
        ]
    }

    response = await client.post("/api/definitions/import", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["index"] == 0
