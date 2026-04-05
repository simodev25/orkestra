"""API tests for agent registry endpoints."""


async def _seed_test_family(client, family_id="analysis", label="Analysis"):
    """Helper: create a family for tests."""
    await client.post("/api/families", json={
        "id": family_id, "label": label, "description": "Test family"
    })


async def _seed_test_skill(client, skill_id="web_research", family_id="analysis"):
    """Helper: create a skill for tests."""
    await client.post("/api/skills", json={
        "skill_id": skill_id,
        "label": "Web Research",
        "category": "execution",
        "description": "Research skill",
        "behavior_templates": ["Search the web"],
        "output_guidelines": ["Cite sources"],
        "allowed_families": [family_id],
    })


async def test_create_agent(client):
    await _seed_test_family(client)
    resp = await client.post("/api/agents", json={
        "id": "test_agent",
        "name": "Test Agent",
        "family_id": "analysis",
        "purpose": "Test agent for API tests",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == "test_agent"
    assert resp.json()["family_id"] == "analysis"
    assert resp.json()["status"] == "draft"


async def test_agent_lifecycle_via_api(client):
    await _seed_test_family(client)
    await client.post("/api/agents", json={
        "id": "lc_agent", "name": "LC Agent",
        "family_id": "analysis", "purpose": "Lifecycle test agent via API",
    })
    for status in ["tested", "registered", "active"]:
        resp = await client.patch("/api/agents/lc_agent/status", json={"status": status})
        assert resp.status_code == 200
    assert resp.json()["status"] == "active"


async def test_list_agents_by_family(client):
    await _seed_test_family(client, "analysis", "Analysis")
    await _seed_test_family(client, "control", "Control")
    await client.post("/api/agents", json={"id": "a1", "name": "A1", "family_id": "analysis", "purpose": "Agent A1 test"})
    await client.post("/api/agents", json={"id": "a2", "name": "A2", "family_id": "control", "purpose": "Agent A2 test"})
    resp = await client.get("/api/agents?family=analysis")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_invalid_transition_returns_400(client):
    await _seed_test_family(client, "test", "Test")
    await client.post("/api/agents", json={"id": "bad", "name": "Bad", "family_id": "test", "purpose": "Bad transition test"})
    resp = await client.patch("/api/agents/bad/status", json={"status": "active"})
    assert resp.status_code == 400
