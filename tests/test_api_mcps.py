"""API tests for MCP registry endpoints."""

async def test_create_mcp(client):
    resp = await client.post("/api/mcps", json={
        "id": "doc_parser",
        "name": "Document Parser",
        "purpose": "Parse uploaded documents",
        "effect_type": "read",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == "doc_parser"
    assert resp.json()["effect_type"] == "read"

async def test_invalid_effect_type(client):
    resp = await client.post("/api/mcps", json={
        "id": "bad_mcp", "name": "Bad",
        "purpose": "Invalid effect MCP", "effect_type": "invalid",
    })
    assert resp.status_code == 400

async def test_mcp_lifecycle_via_api(client):
    await client.post("/api/mcps", json={
        "id": "lc_mcp", "name": "LC MCP",
        "purpose": "Lifecycle test MCP via API", "effect_type": "compute",
    })
    for status in ["tested", "registered", "active"]:
        resp = await client.patch("/api/mcps/lc_mcp/status", json={"status": status})
        assert resp.status_code == 200
    assert resp.json()["status"] == "active"

async def test_degraded_and_recovery(client):
    await client.post("/api/mcps", json={"id": "deg", "name": "Deg", "purpose": "Degraded MCP test", "effect_type": "search"})
    for s in ["tested", "registered", "active", "degraded", "active"]:
        resp = await client.patch("/api/mcps/deg/status", json={"status": s})
        assert resp.status_code == 200
    assert resp.json()["status"] == "active"
