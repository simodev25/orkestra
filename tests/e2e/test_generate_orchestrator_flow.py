"""E2E tests — POST /api/agents/generate-orchestrator flow."""
import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

HEADERS = {"X-API-Key": "test-orkestra-api-key"}

VALID_DRAFT = {
    "agent_id": "my_orchestrator",
    "name": "My Orchestrator",
    "family_id": "orchestration",
    "purpose": "Coordinates agents",
    "description": "Manages a sequential pipeline of agents.",
    "skill_ids": ["sequential_routing", "context_propagation"],
    "selection_hints": {
        "routing_keywords": ["orchestrate", "coordinate"],
        "workflow_ids": [],
        "use_case_hint": "Pipeline coordination",
        "requires_grounded_evidence": False,
    },
    "allowed_mcps": [],
    "forbidden_effects": [],
    "criticality": "medium",
    "cost_profile": "medium",
    "limitations": ["Depends on sub-agent reliability"],
    "prompt_content": "You are an orchestrator. Route tasks in sequence to agents.",
    "skills_content": "sequential_routing: Routes tasks\ncontext_propagation: Passes context",
    "version": "1.0.0",
    "status": "draft",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _seed_family(client: AsyncClient, family_id: str = "analysis") -> None:
    """Create a minimal family (idempotent — ignores errors)."""
    await client.post(
        "/api/families",
        json={"id": family_id, "label": "Analysis"},
        headers=HEADERS,
    )


async def _seed_agent(
    client: AsyncClient,
    agent_id: str = "agent_alpha",
    family_id: str = "analysis",
) -> str | None:
    """Create a family + an agent, return agent_id or None."""
    await _seed_family(client, family_id)
    resp = await client.post(
        "/api/agents",
        json={
            "id": agent_id,
            "name": "Agent Alpha",
            "family_id": family_id,
            "purpose": "Does alpha things",
        },
        headers=HEADERS,
    )
    return agent_id if resp.status_code in (200, 201) else None


# ── TestGenerateOrchestratorValidation ────────────────────────────────────────


class TestGenerateOrchestratorValidation:
    """Input validation — no LLM call needed."""

    async def test_missing_both_ids_and_description_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents/generate-orchestrator",
            json={"name": "My Orchestrator"},
            headers=HEADERS,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "agent_ids" in resp.text.lower() or "use_case_description" in resp.text.lower() or "provide" in resp.text.lower()

    async def test_name_too_short_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents/generate-orchestrator",
            json={
                "name": "ab",
                "agent_ids": ["some_agent"],
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    async def test_missing_name_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents/generate-orchestrator",
            json={"agent_ids": ["some_agent"]},
            headers=HEADERS,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    async def test_empty_agent_ids_with_no_description_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents/generate-orchestrator",
            json={"name": "My Orchestrator", "agent_ids": []},
            headers=HEADERS,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


# ── TestGenerateOrchestratorManualMode ────────────────────────────────────────


class TestGenerateOrchestratorManualMode:
    """Manual mode: agent_ids provided, LLM mocked."""

    async def test_manual_mode_success(self, client: AsyncClient):
        await _seed_agent(client, agent_id="agent_alpha", family_id="analysis")
        await _seed_agent(client, agent_id="agent_beta", family_id="analysis")

        with patch(
            "app.services.orchestrator_builder_service._call_llm",
            new_callable=AsyncMock,
            return_value=json.dumps(VALID_DRAFT),
        ):
            resp = await client.post(
                "/api/agents/generate-orchestrator",
                json={
                    "name": "My Orchestrator",
                    "agent_ids": ["agent_alpha", "agent_beta"],
                },
                headers=HEADERS,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["source"] == "llm"
        assert data["selected_agent_ids"] == ["agent_alpha", "agent_beta"]
        assert "name" in data["draft"]

    async def test_manual_mode_unknown_agent_returns_400(self, client: AsyncClient):
        await _seed_agent(client, agent_id="real_agent", family_id="analysis")

        with patch(
            "app.services.orchestrator_builder_service._call_llm",
            new_callable=AsyncMock,
            return_value=json.dumps(VALID_DRAFT),
        ):
            resp = await client.post(
                "/api/agents/generate-orchestrator",
                json={
                    "name": "My Orchestrator",
                    "agent_ids": ["real_agent", "nonexistent_agent"],
                },
                headers=HEADERS,
            )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "not found" in resp.text.lower()

    async def test_manual_mode_with_user_instructions(self, client: AsyncClient):
        await _seed_agent(client, agent_id="agent_alpha", family_id="analysis")
        await _seed_agent(client, agent_id="agent_beta", family_id="analysis")

        with patch(
            "app.services.orchestrator_builder_service._call_llm",
            new_callable=AsyncMock,
            return_value=json.dumps(VALID_DRAFT),
        ):
            resp = await client.post(
                "/api/agents/generate-orchestrator",
                json={
                    "name": "My Orchestrator",
                    "agent_ids": ["agent_alpha", "agent_beta"],
                    "user_instructions": "Focus on speed",
                },
                headers=HEADERS,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


# ── TestGenerateOrchestratorAutoMode ─────────────────────────────────────────


class TestGenerateOrchestratorAutoMode:
    """Auto mode: use_case_description provided, agent_ids empty."""

    async def test_auto_mode_success(self, client: AsyncClient):
        await _seed_agent(client, agent_id="agent_alpha", family_id="analysis")
        await _seed_agent(client, agent_id="agent_beta", family_id="analysis")

        with patch(
            "app.services.orchestrator_builder_service._call_llm",
            new_callable=AsyncMock,
            return_value=json.dumps(VALID_DRAFT),
        ):
            resp = await client.post(
                "/api/agents/generate-orchestrator",
                json={
                    "name": "Hotel Pipeline",
                    "agent_ids": [],
                    "use_case_description": "Hotel search pipeline",
                },
                headers=HEADERS,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data["selected_agent_ids"], list)

    async def test_auto_mode_empty_description_returns_400(self, client: AsyncClient):
        resp = await client.post(
            "/api/agents/generate-orchestrator",
            json={
                "name": "My Orchestrator",
                "agent_ids": [],
                "use_case_description": "",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"


# ── TestGenerateOrchestratorLLMError ─────────────────────────────────────────


class TestGenerateOrchestratorLLMError:
    """LLM failure scenarios."""

    async def test_llm_exception_returns_503(self, client: AsyncClient):
        await _seed_agent(client, agent_id="agent_alpha", family_id="analysis")
        await _seed_agent(client, agent_id="agent_beta", family_id="analysis")

        with patch(
            "app.services.orchestrator_builder_service._call_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Ollama unreachable"),
        ):
            resp = await client.post(
                "/api/agents/generate-orchestrator",
                json={
                    "name": "My Orchestrator",
                    "agent_ids": ["agent_alpha", "agent_beta"],
                },
                headers=HEADERS,
            )

        assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text}"

    async def test_llm_invalid_json_returns_400(self, client: AsyncClient):
        """_parse_llm_json raises ValueError for invalid JSON → HTTPException 400."""
        await _seed_agent(client, agent_id="agent_alpha", family_id="analysis")
        await _seed_agent(client, agent_id="agent_beta", family_id="analysis")

        with patch(
            "app.services.orchestrator_builder_service._call_llm",
            new_callable=AsyncMock,
            return_value="this is not json",
        ):
            resp = await client.post(
                "/api/agents/generate-orchestrator",
                json={
                    "name": "My Orchestrator",
                    "agent_ids": ["agent_alpha", "agent_beta"],
                },
                headers=HEADERS,
            )

        # ValueError from _parse_llm_json → HTTPException 400
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
