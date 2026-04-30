"""E2E tests for generate-draft and save-generated-draft flow."""

from app.services import agent_generation_service


async def test_generate_draft_without_heuristic_default_families(client):
    await client.post("/api/families", json={"id": "compliance", "label": "Compliance"})

    response = await client.post(
        "/api/agents/generate-draft",
        json={
            "intent": "Generate a compliance-focused agent for procurement review.",
            "preferred_family": "compliance",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["family_id"] == "compliance"


async def test_generate_draft_then_save_succeeds(client):
    await client.post("/api/families", json={"id": "compliance", "label": "Compliance"})
    for skill_id, label in [
        ("context_gap_detection", "Context Gap Detection"),
        ("document_analysis", "Document Analysis"),
        ("source_comparison", "Source Comparison"),
    ]:
        await client.post(
            "/api/skills",
            json={
                "skill_id": skill_id,
                "label": label,
                "category": "analysis",
                "description": f"{label} skill",
                "behavior_templates": [f"Apply {label}"],
                "output_guidelines": ["Be precise"],
                "allowed_families": ["compliance"],
            },
        )

    generate_response = await client.post(
        "/api/agents/generate-draft",
        json={
            "intent": "Create a compliance analyst for public procurement checks.",
            "preferred_family": "compliance",
        },
    )
    assert generate_response.status_code == 200

    draft = generate_response.json()["draft"]
    save_response = await client.post("/api/agents/save-generated-draft", json={"draft": draft})

    assert save_response.status_code == 201


async def test_fallback_heuristic_normalizes_family_to_existing(client, monkeypatch):
    await client.post("/api/families", json={"id": "compliance", "label": "Compliance"})

    async def _boom(prompt: str, db):
        raise RuntimeError("forced llm failure")

    monkeypatch.setattr(agent_generation_service, "_call_llm", _boom)

    response = await client.post(
        "/api/agents/generate-draft",
        json={
            "intent": "Generate a compliance analyst for procurement checks.",
            "preferred_family": "compliance",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "heuristic_template"
    assert payload["draft"]["family_id"] == "compliance"
