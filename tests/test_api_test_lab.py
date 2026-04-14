# tests/test_api_test_lab.py
"""Tests API pour les routes /api/test-lab (scenarios CRUD + run launch)."""
from unittest.mock import patch, AsyncMock


MINIMAL_SCENARIO = {
    "name": "Test Scenario",
    "agent_id": "agent_under_test",
    "input_prompt": "Resolve entity for ACME Corp",
    "assertions": [],
}

# Payload minimal pour créer un agent dans le registry (requis par le run launch)
MINIMAL_AGENT = {
    "id": "agent_under_test",
    "name": "Agent Under Test",
    "family_id": "analysis",
    "purpose": "Test agent for test-lab runs",
}

MINIMAL_FAMILY = {
    "id": "analysis",
    "label": "Analysis",
    "description": "Analysis family",
}


async def _seed_agent(client):
    """Helper : crée famille + agent pour les tests de run launch."""
    await client.post("/api/families", json=MINIMAL_FAMILY)
    await client.post("/api/agents", json=MINIMAL_AGENT)


# ── Smoke tests ────────────────────────────────────────────────────────────────

async def test_list_scenarios_empty(client):
    resp = await client.get("/api/test-lab/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] == 0


async def test_get_scenario_nonexistent_returns_404(client):
    resp = await client.get("/api/test-lab/scenarios/nonexistent")
    assert resp.status_code == 404


async def test_delete_scenario_nonexistent_returns_404(client):
    resp = await client.delete("/api/test-lab/scenarios/nonexistent")
    assert resp.status_code == 404


async def test_list_runs_empty(client):
    resp = await client.get("/api/test-lab/runs")
    assert resp.status_code == 200


async def test_get_run_nonexistent_returns_404(client):
    resp = await client.get("/api/test-lab/runs/nonexistent")
    assert resp.status_code == 404


# ── Scenario CRUD ─────────────────────────────────────────────────────────────

async def test_create_scenario_minimal(client):
    resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Scenario"
    assert data["agent_id"] == "agent_under_test"
    assert "id" in data


async def test_create_scenario_returns_id_with_prefix(client):
    resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    assert resp.status_code == 201
    assert resp.json()["id"].startswith("scn_")


async def test_get_scenario_after_create(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/test-lab/scenarios/{scenario_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == scenario_id


async def test_list_scenarios_after_create(client):
    await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    await client.post("/api/test-lab/scenarios", json={**MINIMAL_SCENARIO, "name": "Scenario 2"})

    resp = await client.get("/api/test-lab/scenarios")
    assert resp.json()["total"] >= 2


async def test_list_scenarios_filter_by_agent_id(client):
    await client.post("/api/test-lab/scenarios", json={**MINIMAL_SCENARIO, "agent_id": "agent_a"})
    await client.post("/api/test-lab/scenarios", json={**MINIMAL_SCENARIO, "agent_id": "agent_b"})

    resp = await client.get("/api/test-lab/scenarios?agent_id=agent_a")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["agent_id"] == "agent_a" for item in items)


async def test_update_scenario_name(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/test-lab/scenarios/{scenario_id}",
        json={"name": "Updated Name"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Name"


async def test_delete_scenario_returns_204(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/test-lab/scenarios/{scenario_id}")
    assert del_resp.status_code == 204


async def test_get_deleted_scenario_returns_404(client):
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]
    await client.delete(f"/api/test-lab/scenarios/{scenario_id}")

    get_resp = await client.get(f"/api/test-lab/scenarios/{scenario_id}")
    assert get_resp.status_code == 404


async def test_create_scenario_with_assertions(client):
    payload = {
        **MINIMAL_SCENARIO,
        "assertions": [
            {"type": "tool_called", "target": "search_tool", "critical": True}
        ],
    }
    resp = await client.post("/api/test-lab/scenarios", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["assertions"]) == 1
    assert data["assertions"][0]["type"] == "tool_called"


# ── Run launch (mocked) ────────────────────────────────────────────────────────

async def test_launch_run_creates_run_record(client):
    await _seed_agent(client)
    create_resp = await client.post("/api/test-lab/scenarios", json=MINIMAL_SCENARIO)
    scenario_id = create_resp.json()["id"]

    with patch(
        "app.services.test_lab.orchestrator_agent.run_orchestrated_test",
        new_callable=AsyncMock,
    ):
        run_resp = await client.post(f"/api/test-lab/scenarios/{scenario_id}/run")

    assert run_resp.status_code == 200
    data = run_resp.json()
    assert "id" in data
    assert data["id"].startswith("trun_")


async def test_launch_run_on_nonexistent_scenario_returns_404(client):
    resp = await client.post("/api/test-lab/scenarios/nonexistent/run")
    assert resp.status_code == 404
