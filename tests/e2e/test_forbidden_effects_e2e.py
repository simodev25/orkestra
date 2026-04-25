"""Live E2E tests for forbidden_effects enforcement on word_test_agent."""

from __future__ import annotations

import uuid

import httpx
import pytest


BASE_URL = "http://localhost:8200"
HEADERS = {"X-API-Key": "test-orkestra-api-key"}
AGENT_ID = "word_test_agent"
WORD_MCP_ID = "ms1rbfml"


@pytest.fixture
async def api_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=60.0) as client:
        yield client


def _tool_names(mcp_payload: dict) -> set[str]:
    preview = mcp_payload.get("obot_server", {}).get("tool_preview", [])
    return {tool.get("name", "") for tool in preview if isinstance(tool, dict)}


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_word_test_agent_forbidden_effects_contains_expected_values(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(f"/api/agents/{AGENT_ID}")
    assert response.status_code == 200, response.text

    payload = response.json()
    forbidden = set(payload.get("forbidden_effects") or [])
    assert "write" in forbidden
    assert "act" in forbidden
    assert "generate" in forbidden


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_word_test_agent_prompt_does_not_invite_write_doc(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(f"/api/agents/{AGENT_ID}")
    assert response.status_code == 200, response.text

    prompt_content = (response.json().get("prompt_content") or "").lower()
    assert "call write_doc" not in prompt_content or "do not call write_doc" in prompt_content
    assert "not authorized" in prompt_content or "read-only" in prompt_content


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_word_mcp_catalog_contains_write_and_read_tools(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(f"/api/mcp-catalog/{WORD_MCP_ID}")
    assert response.status_code == 200, response.text

    tool_names = _tool_names(response.json())
    assert "write_doc" in tool_names
    assert "list_docs" in tool_names


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_write_doc_invocation_is_denied_and_recorded(
    api_client: httpx.AsyncClient,
) -> None:
    task = (
        "Call write_doc with doc_name forbidden-effects-e2e-"
        f"{uuid.uuid4().hex}.docx and doc_content hello"
    )
    run_response = await api_client.post(
        f"/api/agents/{AGENT_ID}/test-run",
        json={"task": task},
    )
    assert run_response.status_code == 200, run_response.text

    run_payload = run_response.json()
    run_id = run_payload.get("id")
    assert run_id, f"Missing run id in payload: {run_payload}"

    denials_response = await api_client.get(f"/api/runs/{run_id}/effect-denials")
    assert denials_response.status_code == 200, denials_response.text
    denials = denials_response.json()
    assert isinstance(denials, list)
    assert denials, (
        "Expected at least one denial for write_doc invocation, got none. "
        f"Run payload: {run_payload}"
    )

    write_denials = [d for d in denials if "write" in (d.get("effects") or [])]
    assert write_denials, f"Expected denial including 'write' effect, got: {denials}"


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_create_agent_without_forbidden_effects_is_allowed(
    api_client: httpx.AsyncClient,
) -> None:
    temp_agent_id = f"e2e-readonly-{uuid.uuid4().hex[:8]}"

    create_response = await api_client.post(
        "/api/agents",
        json={
            "id": temp_agent_id,
            "name": "E2E Read-Only Candidate",
            "family_id": "analysis",
            "purpose": "Temporary E2E validation agent",
        },
    )
    assert create_response.status_code in (200, 201), create_response.text

    try:
        get_response = await api_client.get(f"/api/agents/{temp_agent_id}")
        assert get_response.status_code == 200, get_response.text
        forbidden = get_response.json().get("forbidden_effects")
        assert forbidden in (None, []), f"Expected None or [], got {forbidden}"
    finally:
        delete_response = await api_client.delete(f"/api/agents/{temp_agent_id}")
        assert delete_response.status_code in (200, 204, 404), delete_response.text


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_patch_forbidden_effects_persists_then_restore(
    api_client: httpx.AsyncClient,
) -> None:
    original_response = await api_client.get(f"/api/agents/{AGENT_ID}")
    assert original_response.status_code == 200, original_response.text
    original_payload = original_response.json()
    original_forbidden = original_payload.get("forbidden_effects") or []

    try:
        patch_response = await api_client.patch(
            f"/api/agents/{AGENT_ID}",
            json={"forbidden_effects": ["write"]},
        )
        assert patch_response.status_code == 200, patch_response.text

        verify_response = await api_client.get(f"/api/agents/{AGENT_ID}")
        assert verify_response.status_code == 200, verify_response.text
        assert verify_response.json().get("forbidden_effects") == ["write"]
    finally:
        restore_response = await api_client.patch(
            f"/api/agents/{AGENT_ID}",
            json={"forbidden_effects": original_forbidden},
        )
        assert restore_response.status_code == 200, restore_response.text
