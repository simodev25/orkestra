"""API tests for namespace CRUD and protections."""


async def _seed_test_family(client, family_id="analysis", label="Analysis"):
    await client.post(
        "/api/families",
        json={"id": family_id, "label": label, "description": "Test family"},
    )


async def _create_agent(client, agent_id: str, namespace_slug: str | None = None):
    headers = {}
    if namespace_slug is not None:
        headers["X-Namespace"] = namespace_slug
    return await client.post(
        "/api/agents",
        json={
            "id": agent_id,
            "name": f"Agent {agent_id}",
            "family_id": "analysis",
            "purpose": "Namespace CRUD reference test agent",
        },
        headers=headers,
    )


async def test_namespace_crud_happy_path(client):
    create_resp = await client.post(
        "/api/namespaces",
        json={"name": "Team Alpha", "slug": "team-alpha", "description": "Alpha team"},
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["slug"] == "team-alpha"

    list_resp = await client.get("/api/namespaces?limit=10&offset=0")
    assert list_resp.status_code == 200
    assert any(item["slug"] == "team-alpha" for item in list_resp.json()["items"])

    get_resp = await client.get("/api/namespaces/team-alpha")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Team Alpha"

    update_resp = await client.put(
        "/api/namespaces/team-alpha",
        json={"name": "Team Alpha Updated", "description": "Updated description"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Team Alpha Updated"

    delete_resp = await client.delete("/api/namespaces/team-alpha")
    assert delete_resp.status_code == 204


async def test_namespace_slug_conflict_returns_409(client):
    first = await client.post(
        "/api/namespaces",
        json={"name": "Team Alpha", "slug": "team-alpha"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/namespaces",
        json={"name": "Another Team Alpha", "slug": "team-alpha"},
    )
    assert second.status_code == 409


async def test_delete_referenced_namespace_returns_409(client):
    await _seed_test_family(client)
    ns_resp = await client.post(
        "/api/namespaces",
        json={"name": "Team Alpha", "slug": "team-alpha"},
    )
    assert ns_resp.status_code == 201

    agent_resp = await _create_agent(client, "agent_team_alpha", namespace_slug="team-alpha")
    assert agent_resp.status_code == 201

    delete_resp = await client.delete("/api/namespaces/team-alpha")
    assert delete_resp.status_code == 409


async def test_delete_default_namespace_returns_409(client):
    delete_resp = await client.delete("/api/namespaces/default")
    assert delete_resp.status_code == 409
