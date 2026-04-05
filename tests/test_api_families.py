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


async def test_delete_family_with_agents_blocked(client):
    await client.post("/api/families", json={"id": "used_fam", "label": "Used"})
    await client.post("/api/agents", json={
        "id": "blocker", "name": "Blocker", "family_id": "used_fam", "purpose": "Block delete test"
    })
    resp = await client.delete("/api/families/used_fam")
    assert resp.status_code == 409
    assert "Cannot delete" in resp.json()["detail"]
