"""Tests E2E — flux Test Lab : create scenario → launch run → check status."""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

HEADERS = {"X-API-Key": "test-orkestra-api-key"}

# ── Helpers ────────────────────────────────────────────────────────────────────

async def _seed_family(client: AsyncClient, family_id: str = "test_family") -> None:
    """Créer une famille minimale (idempotent — ignore les erreurs)."""
    await client.post(
        "/api/families",
        json={"id": family_id, "label": "Test Family E2E", "description": "Family for E2E tests"},
        headers=HEADERS,
    )


async def _create_agent(client: AsyncClient, agent_id: str = "e2e_agent") -> str | None:
    """Créer une famille + un agent minimal, retourner l'agent_id ou None."""
    await _seed_family(client)
    resp = await client.post(
        "/api/agents",
        json={
            "id": agent_id,
            "name": "E2E Test Agent",
            "family_id": "test_family",
            "purpose": "Agent used for E2E test lab tests",
        },
        headers=HEADERS,
    )
    if resp.status_code in (200, 201):
        return resp.json().get("id")
    return None


async def _create_scenario(
    client: AsyncClient,
    agent_id: str,
    name: str = "E2E Test Scenario",
) -> str | None:
    """Créer un scénario minimal, retourner son ID ou None."""
    resp = await client.post(
        "/api/test-lab/scenarios",
        json={
            "name": name,
            "agent_id": agent_id,
            "input_prompt": "Hello agent, run a test.",
            "assertions": [],
        },
        headers=HEADERS,
    )
    if resp.status_code in (200, 201):
        return resp.json().get("id")
    return None


# ── Smoke tests sans données ───────────────────────────────────────────────────


class TestSmoke:
    @pytest.mark.asyncio
    async def test_list_scenarios_empty_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/test-lab/scenarios", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_runs_empty_returns_200(self, client: AsyncClient):
        resp = await client.get("/api/test-lab/runs", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent_scenario_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/test-lab/scenarios/nonexistent-id", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_run_returns_404(self, client: AsyncClient):
        resp = await client.get("/api/test-lab/runs/nonexistent-id", headers=HEADERS)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_scenario_missing_body_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/test-lab/scenarios", json={}, headers=HEADERS)
        assert resp.status_code == 422


# ── Tests de création de scénario ─────────────────────────────────────────────


class TestScenarioCreation:
    @pytest.mark.asyncio
    async def test_create_minimal_scenario(self, client: AsyncClient):
        agent_id = await _create_agent(client)
        if not agent_id:
            pytest.skip("Cannot create agent — skipping scenario test")

        resp = await client.post(
            "/api/test-lab/scenarios",
            json={
                "name": "Minimal Test Scenario",
                "agent_id": agent_id,
                "input_prompt": "Hello agent",
                "assertions": [],
            },
            headers=HEADERS,
        )
        assert resp.status_code in (200, 201), f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["name"] == "Minimal Test Scenario"
        assert data["agent_id"] == agent_id

    @pytest.mark.asyncio
    async def test_get_created_scenario(self, client: AsyncClient):
        agent_id = await _create_agent(client, agent_id="e2e_agent_get")
        if not agent_id:
            pytest.skip("Cannot create agent")

        scenario_id = await _create_scenario(client, agent_id, name="Readable Scenario")
        if not scenario_id:
            pytest.skip("Cannot create scenario")

        get_resp = await client.get(f"/api/test-lab/scenarios/{scenario_id}", headers=HEADERS)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == scenario_id

    @pytest.mark.asyncio
    async def test_list_scenarios_after_creation(self, client: AsyncClient):
        agent_id = await _create_agent(client, agent_id="e2e_agent_list")
        if not agent_id:
            pytest.skip("Cannot create agent")

        scenario_id = await _create_scenario(client, agent_id, name="Listed Scenario")
        if not scenario_id:
            pytest.skip("Cannot create scenario")

        list_resp = await client.get("/api/test-lab/scenarios", headers=HEADERS)
        assert list_resp.status_code == 200
        body = list_resp.json()
        # La route retourne {"items": [...], "total": N, ...}
        items = body.get("items", body) if isinstance(body, dict) else body
        assert len(items) >= 1

    @pytest.mark.asyncio
    async def test_create_scenario_with_assertions(self, client: AsyncClient):
        agent_id = await _create_agent(client, agent_id="e2e_agent_assert")
        if not agent_id:
            pytest.skip("Cannot create agent")

        resp = await client.post(
            "/api/test-lab/scenarios",
            json={
                "name": "Scenario With Assertions",
                "agent_id": agent_id,
                "input_prompt": "Do something measurable",
                "assertions": [
                    {"type": "no_tool_failures", "critical": True},
                    {"type": "final_status_is", "expected": "done", "critical": False},
                ],
            },
            headers=HEADERS,
        )
        assert resp.status_code in (200, 201), f"Got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert len(data["assertions"]) == 2


# ── Tests de lancement de run ─────────────────────────────────────────────────


class TestRunFlow:
    @pytest.mark.asyncio
    async def test_launch_run_creates_run_record(self, client: AsyncClient):
        agent_id = await _create_agent(client, agent_id="e2e_agent_run1")
        if not agent_id:
            pytest.skip("Cannot create agent")

        scenario_id = await _create_scenario(client, agent_id, name="Run Test Scenario 1")
        if not scenario_id:
            pytest.skip("Cannot create scenario")

        with patch("app.services.test_lab.orchestrator_agent.run_orchestrated_test", new_callable=AsyncMock):
            run_resp = await client.post(
                f"/api/test-lab/scenarios/{scenario_id}/run",
                headers=HEADERS,
            )

        assert run_resp.status_code in (200, 201, 202), (
            f"Got {run_resp.status_code}: {run_resp.text}"
        )
        data = run_resp.json()
        assert "id" in data
        assert data.get("status") in ("queued", "running", "created", "pending")

    @pytest.mark.asyncio
    async def test_run_retrievable_after_launch(self, client: AsyncClient):
        agent_id = await _create_agent(client, agent_id="e2e_agent_run2")
        if not agent_id:
            pytest.skip("Cannot create agent")

        scenario_id = await _create_scenario(client, agent_id, name="Run Test Scenario 2")
        if not scenario_id:
            pytest.skip("Cannot create scenario")

        with patch("app.services.test_lab.orchestrator_agent.run_orchestrated_test", new_callable=AsyncMock):
            run_resp = await client.post(
                f"/api/test-lab/scenarios/{scenario_id}/run",
                headers=HEADERS,
            )

        if run_resp.status_code not in (200, 201, 202):
            pytest.skip(f"Run launch failed: {run_resp.status_code} — {run_resp.text}")

        run_id = run_resp.json()["id"]
        get_resp = await client.get(f"/api/test-lab/runs/{run_id}", headers=HEADERS)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == run_id

    @pytest.mark.asyncio
    async def test_run_scenario_not_found_returns_404(self, client: AsyncClient):
        with patch("app.services.test_lab.orchestrator_agent.run_orchestrated_test", new_callable=AsyncMock):
            resp = await client.post(
                "/api/test-lab/scenarios/does-not-exist/run",
                headers=HEADERS,
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_runs_after_launch(self, client: AsyncClient):
        agent_id = await _create_agent(client, agent_id="e2e_agent_run3")
        if not agent_id:
            pytest.skip("Cannot create agent")

        scenario_id = await _create_scenario(client, agent_id, name="Run Test Scenario 3")
        if not scenario_id:
            pytest.skip("Cannot create scenario")

        with patch("app.services.test_lab.orchestrator_agent.run_orchestrated_test", new_callable=AsyncMock):
            run_resp = await client.post(
                f"/api/test-lab/scenarios/{scenario_id}/run",
                headers=HEADERS,
            )

        if run_resp.status_code not in (200, 201, 202):
            pytest.skip(f"Run launch failed: {run_resp.status_code}")

        list_resp = await client.get("/api/test-lab/runs", headers=HEADERS)
        assert list_resp.status_code == 200
        body = list_resp.json()
        items = body.get("items", body) if isinstance(body, dict) else body
        assert len(items) >= 1
