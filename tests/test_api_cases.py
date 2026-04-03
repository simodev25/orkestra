"""API tests for case endpoints."""

async def test_convert_request_to_case(client):
    resp = await client.post("/api/requests", json={
        "title": "Case test",
        "request_text": "Analyze this",
        "criticality": "high",
    })
    req_id = resp.json()["id"]
    await client.post(f"/api/requests/{req_id}/submit")
    resp = await client.post(f"/api/cases/{req_id}/convert")
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "ready_for_planning"
    assert data["request_id"] == req_id

async def test_list_cases(client):
    resp = await client.post("/api/requests", json={"title": "T", "request_text": "t"})
    req_id = resp.json()["id"]
    await client.post(f"/api/requests/{req_id}/submit")
    await client.post(f"/api/cases/{req_id}/convert")
    resp = await client.get("/api/cases")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
