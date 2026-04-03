"""Tests for approval service and API."""

import pytest
from app.models.approval import ApprovalRequest
from app.models.run import Run
from app.models.enums import ApprovalStatus, RunStatus
from app.services.approval_service import (
    create_approval, assign_reviewer, approve, reject, request_refinement
)


async def _setup_run(db_session, status="waiting_review"):
    run = Run(case_id="case_1", plan_id="plan_1", status=status)
    db_session.add(run)
    await db_session.flush()
    return run


class TestApprovalService:
    async def test_create_approval(self, db_session):
        run = await _setup_run(db_session)
        await db_session.commit()
        a = await create_approval(db_session, run.id, "case_1", "plan_review", "High criticality")
        await db_session.commit()
        assert a.status == "requested"
        assert a.approval_type == "plan_review"

    async def test_full_approve_flow(self, db_session):
        run = await _setup_run(db_session)
        await db_session.commit()
        a = await create_approval(db_session, run.id, "case_1", "plan_review", "Review needed")
        await db_session.commit()
        a = await assign_reviewer(db_session, a.id, "reviewer@company.com")
        await db_session.commit()
        assert a.status == "pending"
        a = await approve(db_session, a.id, "Looks good")
        await db_session.commit()
        assert a.status == "approved"
        assert a.decision_comment == "Looks good"
        # Run should resume
        await db_session.refresh(run)
        assert run.status == "running"

    async def test_reject_blocks_run(self, db_session):
        run = await _setup_run(db_session)
        await db_session.commit()
        a = await create_approval(db_session, run.id, "case_1", "plan_review", "Review needed")
        await db_session.commit()
        a = await assign_reviewer(db_session, a.id, "reviewer@company.com")
        await db_session.commit()
        a = await reject(db_session, a.id, "Insufficient evidence")
        await db_session.commit()
        assert a.status == "rejected"
        await db_session.refresh(run)
        assert run.status == "blocked"

    async def test_refine_required(self, db_session):
        run = await _setup_run(db_session)
        await db_session.commit()
        a = await create_approval(db_session, run.id, "case_1", "plan_review", "Review needed")
        await db_session.commit()
        a = await assign_reviewer(db_session, a.id, "reviewer@company.com")
        await db_session.commit()
        a = await request_refinement(db_session, a.id, "Need more data")
        await db_session.commit()
        assert a.status == "refine_required"


class TestApprovalAPI:
    async def test_create_and_list_approvals(self, client):
        resp = await client.post("/api/approvals", json={
            "run_id": "run_1", "case_id": "case_1",
            "approval_type": "plan_review", "reason": "High criticality",
        })
        assert resp.status_code == 201
        assert resp.json()["status"] == "requested"

        resp = await client.get("/api/approvals")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_approve_via_api(self, client):
        resp = await client.post("/api/approvals", json={
            "run_id": "run_1", "case_id": "case_1",
            "approval_type": "review", "reason": "Test",
        })
        aid = resp.json()["id"]
        await client.post(f"/api/approvals/{aid}/assign", json={"assigned_to": "bob"})
        resp = await client.post(f"/api/approvals/{aid}/approve", json={"comment": "OK"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_get_nonexistent_approval(self, client):
        resp = await client.get("/api/approvals/nonexistent")
        assert resp.status_code == 404
