"""API tests for agent registry endpoints."""

async def test_create_agent(client):
    resp = await client.post("/api/agents", json={
        "id": "test_agent",
        "name": "Test Agent",
        "family": "analysis",
        "purpose": "Test agent for API tests",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == "test_agent"
    assert resp.json()["status"] == "draft"

async def test_agent_lifecycle_via_api(client):
    await client.post("/api/agents", json={
        "id": "lc_agent", "name": "LC Agent",
        "family": "analysis", "purpose": "Lifecycle test agent via API",
    })
    for status in ["tested", "registered", "active"]:
        resp = await client.patch("/api/agents/lc_agent/status", json={"status": status})
        assert resp.status_code == 200
    assert resp.json()["status"] == "active"

async def test_list_agents_by_family(client):
    await client.post("/api/agents", json={"id": "a1", "name": "A1", "family": "analysis", "purpose": "Agent A1 test"})
    await client.post("/api/agents", json={"id": "a2", "name": "A2", "family": "control", "purpose": "Agent A2 test"})
    resp = await client.get("/api/agents?family=analysis")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

async def test_invalid_transition_returns_400(client):
    await client.post("/api/agents", json={"id": "bad", "name": "Bad", "family": "test", "purpose": "Bad transition test"})
    resp = await client.patch("/api/agents/bad/status", json={"status": "active"})
    assert resp.status_code == 400
