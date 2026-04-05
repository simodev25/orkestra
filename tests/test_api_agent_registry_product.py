"""Product-level API tests for Agent Registry and AI draft generation."""


async def test_agent_registry_stats_and_update(client):
    await client.post("/api/families", json={"id": "analyst", "label": "Analyst"})
    create_resp = await client.post(
        "/api/agents",
        json={
            "id": "registry_agent",
            "name": "Registry Agent",
            "family_id": "analyst",
            "purpose": "Collect and structure company legal evidence for due diligence.",
            "status": "draft",
            "skill_ids": [],
            "prompt_content": "Do evidence-first legal lookup.",
            "skills_content": "# skill file",
            "limitations": ["no write actions"],
            "allowed_mcps": ["datagouv_search_mcp"],
        },
    )
    assert create_resp.status_code == 201

    update_resp = await client.patch(
        "/api/agents/registry_agent",
        json={
            "purpose": "Collect legal and procurement evidence for compliance checks.",
            "last_test_status": "passed",
            "usage_count": 4,
            "status": "tested",
            "allowed_mcps": ["datagouv_search_mcp", "boamp_search_adapter"],
        },
    )
    assert update_resp.status_code == 200
    payload = update_resp.json()
    assert payload["last_test_status"] == "passed"
    assert payload["usage_count"] == 4
    assert payload["status"] == "tested"
    assert "boamp_search_adapter" in payload["allowed_mcps"]

    stats_resp = await client.get("/api/agents/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_agents"] >= 1
    assert stats["tested_agents"] >= 1


async def test_generate_agent_draft_and_save(client):
    # Seed family and skills required by the mock LLM generator
    await client.post("/api/families", json={"id": "analyst", "label": "Analyst"})
    for skill_id, label in [
        ("context_gap_detection", "Context Gap Detection"),
        ("document_analysis", "Document Analysis"),
        ("source_comparison", "Source Comparison"),
    ]:
        await client.post("/api/skills", json={
            "skill_id": skill_id,
            "label": label,
            "category": "analysis",
            "description": f"{label} skill",
            "behavior_templates": [f"Apply {label}"],
            "output_guidelines": ["Be precise"],
            "allowed_families": ["analyst"],
        })

    generate_resp = await client.post(
        "/api/agents/generate-draft",
        json={
            "intent": "Create an agent that finds legal company information from a French SIREN and summarizes evidence.",
            "use_case": "company_due_diligence",
            "preferred_family": "analyst",
            "constraints": "No direct write actions",
        },
    )
    assert generate_resp.status_code == 200
    data = generate_resp.json()
    assert data["source"] == "mock_llm"
    assert data["draft"]["status"] == "draft"
    assert len(data["available_mcps"]) >= 1

    save_resp = await client.post("/api/agents/save-generated-draft", json={"draft": data["draft"]})
    assert save_resp.status_code == 201
    saved = save_resp.json()
    assert saved["status"] == "draft"
    assert saved["prompt_content"]
    assert saved["skills_content"]


async def test_save_generated_draft_rejects_invalid_state_and_unknown_mcp(client):
    bad_draft = {
        "id": "bad_generated_agent",
        "name": "Bad Generated Agent",
        "family_id": "analyst",
        "purpose": "Bad generated purpose for validation checks.",
        "description": "desc",
        "skill_ids": ["context_gap_detection"],
        "selection_hints": {"routing_keywords": ["legal"]},
        "allowed_mcps": ["unknown_mcp_id"],
        "forbidden_effects": ["act"],
        "input_contract_ref": "contracts/bad.input.v1",
        "output_contract_ref": "contracts/bad.output.v1",
        "criticality": "high",
        "cost_profile": "medium",
        "limitations": ["no write"],
        "prompt_content": "prompt",
        "skills_content": "skills",
        "owner": "qa",
        "version": "1.0.0",
        "status": "active",
        "suggested_missing_mcps": [],
        "mcp_rationale": {},
    }
    resp = await client.post("/api/agents/save-generated-draft", json={"draft": bad_draft})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "status must be draft or designed" in detail
    assert "unknown ids" in detail


async def test_delete_agent_and_reject_delete_active(client):
    await client.post("/api/families", json={"id": "analyst", "label": "Analyst"})
    create_resp = await client.post(
        "/api/agents",
        json={
            "id": "deletable_agent",
            "name": "Deletable Agent",
            "family_id": "analyst",
            "purpose": "Collect evidence and produce structured summaries for governance.",
            "status": "draft",
            "skill_ids": [],
            "prompt_content": "Collect evidence only.",
            "skills_content": "# skill file",
            "limitations": ["no write actions"],
        },
    )
    assert create_resp.status_code == 201

    delete_resp = await client.delete("/api/agents/deletable_agent")
    assert delete_resp.status_code == 204

    get_resp = await client.get("/api/agents/deletable_agent")
    assert get_resp.status_code == 404

    active_resp = await client.post(
        "/api/agents",
        json={
            "id": "active_agent_delete_blocked",
            "name": "Active Agent",
            "family_id": "analyst",
            "purpose": "Collect evidence and produce structured summaries for governance.",
            "status": "active",
            "skill_ids": [],
            "prompt_content": "Collect evidence only.",
            "skills_content": "# skill file",
            "limitations": ["no write actions"],
        },
    )
    assert active_resp.status_code == 201

    blocked_resp = await client.delete("/api/agents/active_agent_delete_blocked")
    assert blocked_resp.status_code == 400
    assert "Cannot delete an active agent" in blocked_resp.json()["detail"]
