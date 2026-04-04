"""API tests for Obot-backed MCP catalog and Orkestra bindings."""


async def test_list_mcp_catalog_from_obot(client):
    resp = await client.get("/api/mcp-catalog")
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1

    first = payload[0]
    assert "obot_server" in first
    assert "orkestra_binding" in first
    assert "obot_state" in first
    assert "orkestra_state" in first


async def test_sync_import_enable_and_bind_actions(client):
    sync_resp = await client.post("/api/mcp-catalog/sync")
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["total_obot_servers"] >= 1

    import_resp = await client.post(
        "/api/mcp-catalog/import",
        json={"obot_server_ids": ["datagouv_search_mcp"]},
    )
    assert import_resp.status_code == 200
    import_data = import_resp.json()
    assert import_data["imported_count"] == 1

    enable_resp = await client.post("/api/mcp-catalog/datagouv_search_mcp/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["enabled_in_orkestra"] is True

    bind_workflow_resp = await client.post(
        "/api/mcp-catalog/datagouv_search_mcp/bind-workflow",
        json={"workflow_id": "credit_review_default"},
    )
    assert bind_workflow_resp.status_code == 200
    assert "credit_review_default" in bind_workflow_resp.json()["allowed_workflows"]

    bind_family_resp = await client.post(
        "/api/mcp-catalog/datagouv_search_mcp/bind-agent-family",
        json={"agent_family": "research"},
    )
    assert bind_family_resp.status_code == 200
    assert "research" in bind_family_resp.json()["allowed_agent_families"]

    detail_resp = await client.get("/api/mcp-catalog/datagouv_search_mcp")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["obot_server"]["id"] == "datagouv_search_mcp"
    assert detail["orkestra_binding"]["enabled_in_orkestra"] is True
    assert detail["orkestra_state"] == "restricted"


async def test_edit_bindings_and_stats(client):
    await client.post(
        "/api/mcp-catalog/import",
        json={"obot_server_ids": ["web_search_mcp"]},
    )

    patch_resp = await client.patch(
        "/api/mcp-catalog/web_search_mcp/bindings",
        json={
            "enabled_in_orkestra": True,
            "hidden_from_ai_generator": True,
            "risk_level_override": "high",
            "preferred_use_cases": ["due_diligence"],
            "notes": "Needs human review on sensitive dossiers.",
        },
    )
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    assert patch_data["enabled_in_orkestra"] is True
    assert patch_data["hidden_from_ai_generator"] is True
    assert patch_data["risk_level_override"] == "high"

    stats_resp = await client.get("/api/mcp-catalog/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["obot_total"] >= 1
    assert stats["orkestra_enabled"] >= 1
    assert stats["hidden_from_ai_generator"] >= 1
