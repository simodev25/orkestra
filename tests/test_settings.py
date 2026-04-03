"""Tests for settings service and API."""


class TestPolicyProfileAPI:
    async def test_create_policy(self, client):
        resp = await client.post("/api/settings/policy-profiles", json={
            "name": "Default Policy",
            "rules": {"high_criticality_requires_review": True},
            "is_default": True,
        })
        assert resp.status_code == 201
        assert resp.json()["is_default"] is True

    async def test_list_policies(self, client):
        await client.post("/api/settings/policy-profiles", json={"name": "P1"})
        await client.post("/api/settings/policy-profiles", json={"name": "P2"})
        resp = await client.get("/api/settings/policy-profiles")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_get_policy(self, client):
        resp = await client.post("/api/settings/policy-profiles", json={"name": "GetTest"})
        pid = resp.json()["id"]
        resp = await client.get(f"/api/settings/policy-profiles/{pid}")
        assert resp.status_code == 200


class TestBudgetProfileAPI:
    async def test_create_budget(self, client):
        resp = await client.post("/api/settings/budget-profiles", json={
            "name": "Default Budget",
            "max_run_cost": 10.0,
            "soft_limit": 5.0,
            "hard_limit": 10.0,
            "is_default": True,
        })
        assert resp.status_code == 201
        assert resp.json()["hard_limit"] == 10.0

    async def test_list_budgets(self, client):
        await client.post("/api/settings/budget-profiles", json={"name": "B1"})
        await client.post("/api/settings/budget-profiles", json={"name": "B2"})
        resp = await client.get("/api/settings/budget-profiles")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_only_one_default(self, client):
        await client.post("/api/settings/budget-profiles", json={"name": "B1", "is_default": True})
        await client.post("/api/settings/budget-profiles", json={"name": "B2", "is_default": True})
        resp = await client.get("/api/settings/budget-profiles")
        defaults = [b for b in resp.json() if b["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "B2"
