"""API tests for skill endpoints."""


async def _seed_family(client, fid="analysis"):
    await client.post("/api/families", json={"id": fid, "label": fid.title()})


async def test_create_skill(client):
    await _seed_family(client)
    resp = await client.post("/api/skills", json={
        "skill_id": "test_skill",
        "label": "Test Skill",
        "category": "analysis",
        "description": "A test skill",
        "behavior_templates": ["Do analysis"],
        "output_guidelines": ["Be precise"],
        "allowed_families": ["analysis"],
    })
    assert resp.status_code == 201
    assert resp.json()["skill_id"] == "test_skill"
    assert "analysis" in resp.json()["allowed_families"]


async def test_list_skills(client):
    await _seed_family(client)
    await client.post("/api/skills", json={
        "skill_id": "sk1", "label": "SK1", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["analysis"],
    })
    resp = await client.get("/api/skills")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_skills_by_family(client):
    await _seed_family(client, "exec")
    await client.post("/api/skills", json={
        "skill_id": "fam_skill", "label": "FS", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["exec"],
    })
    resp = await client.get("/api/skills/by-family/exec")
    assert resp.status_code == 200
    assert any(s["skill_id"] == "fam_skill" for s in resp.json())


async def test_delete_skill_used_by_agent_archives(client):
    """Deleting a skill referenced by an agent should archive it instead."""
    await _seed_family(client, "block_fam")
    await client.post("/api/skills", json={
        "skill_id": "blocked_sk", "label": "BS", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["block_fam"],
    })
    await client.post("/api/agents", json={
        "id": "sk_user", "name": "SK User", "family_id": "block_fam",
        "purpose": "Uses blocked skill", "skill_ids": ["blocked_sk"],
    })
    resp = await client.delete("/api/skills/blocked_sk")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


async def test_archive_skill(client):
    """Archiving a skill should set status to archived."""
    await _seed_family(client)
    await client.post("/api/skills", json={
        "skill_id": "arch_skill", "label": "AS", "category": "c", "description": "d",
        "behavior_templates": ["b"], "output_guidelines": ["o"], "allowed_families": ["analysis"],
    })
    resp = await client.patch("/api/skills/arch_skill/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"
