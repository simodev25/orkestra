"""API tests for request endpoints."""

async def test_create_request(client):
    resp = await client.post("/api/requests", json={
        "title": "Test request",
        "request_text": "Please analyze this document",
        "criticality": "high",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["title"] == "Test request"

async def test_submit_request(client):
    resp = await client.post("/api/requests", json={
        "title": "Submit test",
        "request_text": "Analyze this",
    })
    req_id = resp.json()["id"]
    resp = await client.post(f"/api/requests/{req_id}/submit")
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"

async def test_list_requests(client):
    await client.post("/api/requests", json={"title": "A", "request_text": "t"})
    await client.post("/api/requests", json={"title": "B", "request_text": "t"})
    resp = await client.get("/api/requests")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

async def test_get_nonexistent_request(client):
    resp = await client.get("/api/requests/nonexistent")
    assert resp.status_code == 404
