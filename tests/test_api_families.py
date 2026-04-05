"""API tests for family endpoints."""


async def test_create_family(client):
    resp = await client.post("/api/families", json={
        "id": "test_fam", "label": "Test Family", "description": "A test family"
    })
    assert resp.status_code == 201
    assert resp.json()["id"] == "test_fam"


async def test_list_families(client):
    await client.post("/api/families", json={"id": "f1", "label": "F1"})
    await client.post("/api/families", json={"id": "f2", "label": "F2"})
    resp = await client.get("/api/families")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


async def test_get_family_detail(client):
    await client.post("/api/families", json={"id": "detail_fam", "label": "Detail"})
    resp = await client.get("/api/families/detail_fam")
    assert resp.status_code == 200
    assert resp.json()["id"] == "detail_fam"
    assert "skills" in resp.json()


async def test_update_family(client):
    await client.post("/api/families", json={"id": "upd_fam", "label": "Old"})
    resp = await client.patch("/api/families/upd_fam", json={"label": "New"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "New"


async def test_delete_family(client):
    await client.post("/api/families", json={"id": "del_fam", "label": "Del"})
    resp = await client.delete("/api/families/del_fam")
    assert resp.status_code == 204


async def test_delete_family_with_agents_archives(client):
    """Deleting a family that is referenced by agents should archive it instead."""
    await client.post("/api/families", json={"id": "used_fam", "label": "Used"})
    await client.post("/api/agents", json={
        "id": "blocker", "name": "Blocker", "family_id": "used_fam", "purpose": "Block delete test"
    })
    resp = await client.delete("/api/families/used_fam")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


async def test_archive_family(client):
    """Archiving a family should set status to archived."""
    await client.post("/api/families", json={"id": "arch_fam", "label": "Archive Test"})
    resp = await client.patch("/api/families/arch_fam/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


async def test_list_families_excludes_archived(client):
    """By default, archived families should not appear in list."""
    await client.post("/api/families", json={"id": "vis_fam", "label": "Visible"})
    await client.post("/api/families", json={"id": "hid_fam", "label": "Hidden"})
    await client.patch("/api/families/hid_fam/archive")
    resp = await client.get("/api/families")
    ids = [f["id"] for f in resp.json()]
    assert "vis_fam" in ids
    assert "hid_fam" not in ids


async def test_list_families_include_archived(client):
    """With include_archived=true, all families should appear."""
    await client.post("/api/families", json={"id": "all_vis", "label": "All Vis"})
    await client.post("/api/families", json={"id": "all_hid", "label": "All Hid"})
    await client.patch("/api/families/all_hid/archive")
    resp = await client.get("/api/families?include_archived=true")
    ids = [f["id"] for f in resp.json()]
    assert "all_vis" in ids
    assert "all_hid" in ids


async def test_agent_rejected_if_family_archived(client):
    """Agent creation should fail if family is archived."""
    await client.post("/api/families", json={"id": "dead_fam", "label": "Dead"})
    await client.patch("/api/families/dead_fam/archive")
    resp = await client.post("/api/agents", json={
        "id": "dead_agent", "name": "Dead Agent",
        "family_id": "dead_fam", "purpose": "Should be rejected",
    })
    assert resp.status_code == 400
    assert "not active" in resp.json()["detail"].lower() or "archived" in resp.json()["detail"].lower()
