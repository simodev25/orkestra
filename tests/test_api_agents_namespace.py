"""API tests for X-Namespace resolution and agent scoping."""


async def _seed_test_family(client, family_id="analysis", label="Analysis"):
    await client.post(
        "/api/families",
        json={"id": family_id, "label": label, "description": "Test family"},
    )


async def _create_namespace(client, slug: str, name: str | None = None):
    return await client.post(
        "/api/namespaces",
        json={"name": name or slug.title(), "slug": slug},
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
            "purpose": "Namespace scoped agent for API tests",
        },
        headers=headers,
    )


async def test_missing_or_empty_header_resolves_to_default(client):
    await _seed_test_family(client)

    create_default_agent = await _create_agent(client, "default_agent")
    assert create_default_agent.status_code == 201

    await _create_namespace(client, "team-alpha", name="Team Alpha")
    create_team_agent = await _create_agent(client, "team_alpha_agent", namespace_slug="team-alpha")
    assert create_team_agent.status_code == 201

    list_default_no_header = await client.get("/api/agents")
    assert list_default_no_header.status_code == 200
    ids_default_no_header = {item["id"] for item in list_default_no_header.json()["items"]}
    assert "default_agent" in ids_default_no_header
    assert "team_alpha_agent" not in ids_default_no_header

    list_default_empty_header = await client.get("/api/agents", headers={"X-Namespace": ""})
    assert list_default_empty_header.status_code == 200
    ids_default_empty_header = {item["id"] for item in list_default_empty_header.json()["items"]}
    assert "default_agent" in ids_default_empty_header
    assert "team_alpha_agent" not in ids_default_empty_header


async def test_invalid_header_format_returns_422(client):
    response = await client.get("/api/agents", headers={"X-Namespace": "Bad_Slug"})
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid namespace slug"


async def test_unknown_header_slug_returns_404(client):
    response = await client.get("/api/agents", headers={"X-Namespace": "does-not-exist"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Namespace not found"}


async def test_list_and_get_agents_are_namespace_scoped(client):
    await _seed_test_family(client)
    await _create_namespace(client, "team-alpha", name="Team Alpha")
    await _create_namespace(client, "team-beta", name="Team Beta")

    create_alpha = await _create_agent(client, "agent_alpha", namespace_slug="team-alpha")
    assert create_alpha.status_code == 201

    create_beta = await _create_agent(client, "agent_beta", namespace_slug="team-beta")
    assert create_beta.status_code == 201

    list_alpha = await client.get("/api/agents", headers={"X-Namespace": "team-alpha"})
    assert list_alpha.status_code == 200
    ids_alpha = {item["id"] for item in list_alpha.json()["items"]}
    assert "agent_alpha" in ids_alpha
    assert "agent_beta" not in ids_alpha

    list_beta = await client.get("/api/agents", headers={"X-Namespace": "team-beta"})
    assert list_beta.status_code == 200
    ids_beta = {item["id"] for item in list_beta.json()["items"]}
    assert "agent_beta" in ids_beta
    assert "agent_alpha" not in ids_beta

    get_mismatch = await client.get("/api/agents/agent_alpha", headers={"X-Namespace": "team-beta"})
    assert get_mismatch.status_code == 404


async def test_create_agent_persists_namespace_from_header(client):
    await _seed_test_family(client)
    await _create_namespace(client, "team-alpha", name="Team Alpha")

    create_resp = await _create_agent(client, "agent_alpha_create", namespace_slug="team-alpha")
    assert create_resp.status_code == 201
    created = create_resp.json()

    get_resp = await client.get("/api/agents/agent_alpha_create", headers={"X-Namespace": "team-alpha"})
    assert get_resp.status_code == 200
    assert get_resp.json()["namespace_id"] == created["namespace_id"]
