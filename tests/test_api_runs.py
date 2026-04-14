# tests/test_api_runs.py
"""Tests API pour les routes runs.py et plans.py."""
from app.models.enums import RunStatus, RunNodeStatus, RunNodeType, PlanStatus, CaseStatus
from app.models.run import Run, RunNode
from app.models.plan import OrchestrationPlan
from app.models.case import Case


async def _seed_case(db_session, case_id: str = "case_test") -> Case:
    case = Case(
        id=case_id,
        request_id="req_test",
        case_type="operational",
        business_context="Test context",
        status=CaseStatus.PLANNING,
    )
    db_session.add(case)
    await db_session.flush()
    return case


async def _seed_plan(db_session, case_id: str = "case_test", plan_id: str = "plan_test") -> OrchestrationPlan:
    plan = OrchestrationPlan(
        id=plan_id,
        case_id=case_id,
        status=PlanStatus.VALIDATED,
        created_by="test",
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


async def _seed_run(
    db_session,
    run_id: str = "run_test",
    case_id: str = "case_test",
    plan_id: str = "plan_test",
    status: str = RunStatus.CREATED,
) -> Run:
    run = Run(id=run_id, case_id=case_id, plan_id=plan_id, status=status)
    db_session.add(run)
    await db_session.flush()
    return run


async def _seed_run_node(db_session, run_id: str = "run_test") -> RunNode:
    node = RunNode(
        run_id=run_id,
        node_type=RunNodeType.SUBAGENT,
        node_ref="agent_test",
        status=RunNodeStatus.PENDING,
        depends_on=[],
        order_index=0,
    )
    db_session.add(node)
    await db_session.flush()
    return node


# ── Smoke tests ────────────────────────────────────────────────────────────────

async def test_list_runs_returns_200_empty(client):
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_run_nonexistent_returns_404(client):
    resp = await client.get("/api/runs/nonexistent_run")
    assert resp.status_code == 404


async def test_get_run_nodes_nonexistent_run(client):
    resp = await client.get("/api/runs/nonexistent_run/nodes")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_start_run_nonexistent_returns_400(client):
    resp = await client.post("/api/runs/nonexistent_run/start")
    assert resp.status_code == 400


async def test_cancel_run_nonexistent_returns_400(client):
    resp = await client.post("/api/runs/nonexistent_run/cancel")
    assert resp.status_code == 400


# ── Run lifecycle via seed DB ─────────────────────────────────────────────────

async def test_get_run_returns_correct_data(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await _seed_run(db_session)
    await db_session.commit()

    resp = await client.get("/api/runs/run_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "run_test"
    assert data["case_id"] == "case_test"
    assert data["plan_id"] == "plan_test"
    assert data["status"] == "created"


async def test_list_runs_filter_by_case_id(client, db_session):
    await _seed_case(db_session, "case_a")
    await _seed_plan(db_session, "case_a", "plan_a")
    await _seed_run(db_session, "run_a", "case_a", "plan_a")

    await _seed_case(db_session, "case_b")
    await _seed_plan(db_session, "case_b", "plan_b")
    await _seed_run(db_session, "run_b", "case_b", "plan_b")
    await db_session.commit()

    resp = await client.get("/api/runs?case_id=case_a")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert "run_a" in ids
    assert "run_b" not in ids


async def test_get_run_nodes_returns_seeded_node(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await _seed_run(db_session)
    await _seed_run_node(db_session)
    await db_session.commit()

    resp = await client.get("/api/runs/run_test/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) == 1
    assert nodes[0]["run_id"] == "run_test"
    assert nodes[0]["node_ref"] == "agent_test"
    assert nodes[0]["status"] == "pending"


async def test_cancel_run_transitions_to_cancelled(client, db_session):
    # Use PLANNED status: RunStateMachine allows planned -> cancelled
    # but not running -> cancelled
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await _seed_run(db_session, status=RunStatus.PLANNED)
    await db_session.commit()

    resp = await client.post("/api/runs/run_test/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ── Plans smoke tests ─────────────────────────────────────────────────────────

async def test_get_plan_nonexistent_returns_404(client):
    resp = await client.get("/api/plans/nonexistent_plan")
    assert resp.status_code == 404


async def test_get_plan_returns_correct_data(client, db_session):
    await _seed_case(db_session)
    await _seed_plan(db_session)
    await db_session.commit()

    resp = await client.get("/api/plans/plan_test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "plan_test"
    assert data["case_id"] == "case_test"
    assert data["status"] == "validated"
