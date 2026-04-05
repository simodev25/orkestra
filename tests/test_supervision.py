"""Tests for supervision service and API."""


async def _setup_full_run(client):
    """Create agents, request, case, plan, run, start it."""
    await client.post("/api/families", json={"id": "analysis", "label": "Analysis"})
    await client.post("/api/agents", json={
        "id": "sup_agent", "name": "Sup Agent", "family_id": "analysis",
        "purpose": "Supervision test agent",
    })
    for s in ["tested", "registered", "active"]:
        await client.patch("/api/agents/sup_agent/status", json={"status": s})

    resp = await client.post("/api/requests", json={
        "title": "Supervision test", "request_text": "Test supervision",
    })
    req_id = resp.json()["id"]
    await client.post(f"/api/requests/{req_id}/submit")

    resp = await client.post(f"/api/cases/{req_id}/convert")
    case_id = resp.json()["id"]

    resp = await client.post(f"/api/cases/{case_id}/plan")
    plan_id = resp.json()["id"]

    resp = await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan_id})
    run_id = resp.json()["id"]
    await client.post(f"/api/runs/{run_id}/start")
    return run_id


class TestSupervisionAPI:
    async def test_get_run_live_state(self, client):
        run_id = await _setup_full_run(client)

        resp = await client.get(f"/api/runs/{run_id}/live-state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["run_status"] == "running"
        assert data["nodes_total"] >= 1
        assert "nodes_by_status" in data

    async def test_get_platform_metrics(self, client):
        await _setup_full_run(client)

        resp = await client.get("/api/metrics/platform")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] >= 1
        assert "runs_by_status" in data

    async def test_live_state_not_found(self, client):
        resp = await client.get("/api/runs/nonexistent/live-state")
        assert resp.status_code == 404
