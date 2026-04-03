"""Tests for orchestration: plan generation, run execution, full flow."""


async def _create_submitted_request(client):
    resp = await client.post("/api/requests", json={
        "title": "Test orchestration",
        "request_text": "Analyze this document",
        "criticality": "medium",
        "use_case": "credit_review",
    })
    req_id = resp.json()["id"]
    await client.post(f"/api/requests/{req_id}/submit")
    return req_id


async def _create_case(client, req_id: str):
    resp = await client.post(f"/api/cases/{req_id}/convert")
    return resp.json()["id"]


async def _register_active_agent(client, agent_id: str, use_cases=None):
    hints = {"use_cases": use_cases} if use_cases else None
    await client.post("/api/agents", json={
        "id": agent_id,
        "name": f"Agent {agent_id}",
        "family": "analysis",
        "purpose": f"Test agent {agent_id} for orchestration",
        "selection_hints": hints,
        "allowed_mcps": ["doc_parser"],
    })
    for status in ["tested", "registered", "active"]:
        await client.patch(f"/api/agents/{agent_id}/status", json={"status": status})


async def _register_active_mcp(client, mcp_id: str, effect_type: str = "read"):
    await client.post("/api/mcps", json={
        "id": mcp_id,
        "name": f"MCP {mcp_id}",
        "purpose": f"Test MCP {mcp_id}",
        "effect_type": effect_type,
        "allowed_agents": ["agent_a", "agent_b"],
    })
    for status in ["tested", "registered", "active"]:
        await client.patch(f"/api/mcps/{mcp_id}/status", json={"status": status})


class TestPlanGeneration:
    async def test_generate_plan_for_case(self, client):
        await _register_active_agent(client, "agent_a", use_cases=["credit_review"])
        await _register_active_mcp(client, "doc_parser")
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        resp = await client.post(f"/api/cases/{case_id}/plan")
        assert resp.status_code == 201
        plan = resp.json()
        assert plan["case_id"] == case_id
        assert plan["status"] == "validated"
        assert len(plan["selected_agents"]) >= 1
        assert plan["estimated_cost"] > 0

    async def test_generate_plan_no_agents(self, client):
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        resp = await client.post(f"/api/cases/{case_id}/plan")
        assert resp.status_code == 201
        plan = resp.json()
        assert plan["selected_agents"] == []

    async def test_get_plan(self, client):
        await _register_active_agent(client, "agent_a")
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        resp = await client.post(f"/api/cases/{case_id}/plan")
        plan_id = resp.json()["id"]

        resp = await client.get(f"/api/plans/{plan_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == plan_id


class TestRunExecution:
    async def test_create_and_start_run(self, client):
        await _register_active_agent(client, "agent_a")
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        plan_resp = await client.post(f"/api/cases/{case_id}/plan")
        plan_id = plan_resp.json()["id"]

        run_resp = await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan_id})
        assert run_resp.status_code == 201
        run = run_resp.json()
        assert run["status"] == "planned"

        start_resp = await client.post(f"/api/runs/{run['id']}/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "running"

    async def test_get_run_nodes(self, client):
        await _register_active_agent(client, "agent_a")
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        plan_resp = await client.post(f"/api/cases/{case_id}/plan")
        plan_id = plan_resp.json()["id"]

        run_resp = await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan_id})
        run_id = run_resp.json()["id"]

        nodes_resp = await client.get(f"/api/runs/{run_id}/nodes")
        assert nodes_resp.status_code == 200
        nodes = nodes_resp.json()
        assert len(nodes) >= 1
        assert nodes[0]["node_ref"] == "agent_a"

    async def test_cancel_run(self, client):
        await _register_active_agent(client, "agent_a")
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        plan_resp = await client.post(f"/api/cases/{case_id}/plan")
        plan_id = plan_resp.json()["id"]

        run_resp = await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan_id})
        run_id = run_resp.json()["id"]

        cancel_resp = await client.post(f"/api/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

    async def test_list_runs(self, client):
        await _register_active_agent(client, "agent_a")
        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        plan_resp = await client.post(f"/api/cases/{case_id}/plan")
        plan_id = plan_resp.json()["id"]

        await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan_id})

        resp = await client.get("/api/runs")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestFullOrchestrationFlow:
    async def test_end_to_end_flow(self, client):
        """Full flow: request → case → plan → run → start → nodes ready."""
        await _register_active_agent(client, "agent_a", use_cases=["credit_review"])
        await _register_active_agent(client, "agent_b", use_cases=["credit_review"])
        await _register_active_mcp(client, "doc_parser")

        req_id = await _create_submitted_request(client)
        case_id = await _create_case(client, req_id)

        plan_resp = await client.post(f"/api/cases/{case_id}/plan")
        assert plan_resp.status_code == 201
        plan = plan_resp.json()
        assert len(plan["selected_agents"]) == 2

        run_resp = await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan["id"]})
        run = run_resp.json()
        assert run["status"] == "planned"

        start_resp = await client.post(f"/api/runs/{run['id']}/start")
        assert start_resp.json()["status"] == "running"

        nodes_resp = await client.get(f"/api/runs/{run['id']}/nodes")
        nodes = nodes_resp.json()
        assert len(nodes) == 2
        # First node should be ready (no deps), second pending (depends on first)
        assert nodes[0]["status"] == "ready"
        assert nodes[1]["status"] == "pending"
