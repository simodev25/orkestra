"""Tests for workflow service and API."""

import pytest
from app.services.workflow_service import validate_graph


class TestGraphValidation:
    def test_empty_graph_valid(self):
        assert validate_graph({}) == []
        assert validate_graph({"nodes": []}) == []

    def test_valid_sequential(self):
        graph = {"nodes": [
            {"node_ref": "a", "depends_on": []},
            {"node_ref": "b", "depends_on": ["a"]},
        ]}
        assert validate_graph(graph) == []

    def test_unknown_dependency(self):
        graph = {"nodes": [
            {"node_ref": "a", "depends_on": ["nonexistent"]},
        ]}
        errors = validate_graph(graph)
        assert any("unknown" in e for e in errors)

    def test_cycle_detected(self):
        graph = {"nodes": [
            {"node_ref": "a", "depends_on": ["b"]},
            {"node_ref": "b", "depends_on": ["a"]},
        ]}
        errors = validate_graph(graph)
        assert any("ycle" in e for e in errors)


class TestWorkflowAPI:
    async def test_create_workflow(self, client):
        resp = await client.post("/api/workflow-definitions", json={
            "name": "Credit Review v1",
            "use_case": "credit_review",
            "execution_mode": "sequential",
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    async def test_create_with_graph(self, client):
        resp = await client.post("/api/workflow-definitions", json={
            "name": "With Graph",
            "graph_definition": {
                "nodes": [
                    {"node_ref": "agent_a", "depends_on": []},
                    {"node_ref": "agent_b", "depends_on": ["agent_a"]},
                ]
            },
        })
        assert resp.status_code == 201

    async def test_create_with_invalid_graph(self, client):
        resp = await client.post("/api/workflow-definitions", json={
            "name": "Bad Graph",
            "graph_definition": {
                "nodes": [
                    {"node_ref": "a", "depends_on": ["b"]},
                    {"node_ref": "b", "depends_on": ["a"]},
                ]
            },
        })
        assert resp.status_code == 400

    async def test_publish_workflow(self, client):
        resp = await client.post("/api/workflow-definitions", json={"name": "Pub Test"})
        wf_id = resp.json()["id"]
        resp = await client.post(f"/api/workflow-definitions/{wf_id}/publish")
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    async def test_validate_workflow(self, client):
        resp = await client.post("/api/workflow-definitions", json={
            "name": "Val Test",
            "graph_definition": {"nodes": [{"node_ref": "a", "depends_on": []}]},
        })
        wf_id = resp.json()["id"]
        resp = await client.post(f"/api/workflow-definitions/{wf_id}/validate")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    async def test_list_workflows(self, client):
        await client.post("/api/workflow-definitions", json={"name": "W1"})
        await client.post("/api/workflow-definitions", json={"name": "W2"})
        resp = await client.get("/api/workflow-definitions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
