"""Tests for audit service and API."""

import pytest
from app.models.run import Run
from app.models.audit import AuditEvent, EvidenceRecord
from app.services.audit_service import (
    get_audit_trail, create_evidence, get_evidence_for_run,
    generate_replay_bundle, get_replay_bundle,
)
from datetime import datetime, timezone


async def _setup_completed_run(db_session):
    run = Run(case_id="case_1", plan_id="plan_1", status="completed")
    db_session.add(run)
    await db_session.flush()
    event = AuditEvent(
        run_id=run.id, event_type="run.completed",
        actor_type="system", actor_ref="test",
        payload={}, timestamp=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    return run


class TestAuditService:
    async def test_get_audit_trail(self, db_session):
        run = await _setup_completed_run(db_session)
        await db_session.commit()
        events = await get_audit_trail(db_session, run.id)
        assert len(events) >= 1

    async def test_create_evidence(self, db_session):
        run = await _setup_completed_run(db_session)
        await db_session.commit()
        ev = await create_evidence(
            db_session, run.id, "agent_output", "agent_a",
            evidence_strength="P2", summary="Found inconsistency",
        )
        await db_session.commit()
        assert ev.source_type == "agent_output"
        records = await get_evidence_for_run(db_session, run.id)
        assert len(records) == 1

    async def test_generate_replay_bundle(self, db_session):
        run = await _setup_completed_run(db_session)
        await db_session.commit()
        bundle = await generate_replay_bundle(db_session, run.id)
        await db_session.commit()
        assert bundle.bundle_status == "ready"
        assert bundle.replayable is True

    async def test_replay_bundle_fails_for_running(self, db_session):
        run = Run(case_id="case_1", plan_id="plan_1", status="running")
        db_session.add(run)
        await db_session.flush()
        await db_session.commit()
        with pytest.raises(ValueError, match="Cannot generate"):
            await generate_replay_bundle(db_session, run.id)


class TestAuditAPI:
    async def _run_full_flow(self, client):
        await client.post("/api/agents", json={
            "id": "aud_agent", "name": "Audit Agent", "family": "analysis",
            "purpose": "Audit test agent",
        })
        for s in ["tested", "registered", "active"]:
            await client.patch("/api/agents/aud_agent/status", json={"status": s})

        resp = await client.post("/api/requests", json={
            "title": "Audit test", "request_text": "Test audit trail",
        })
        req_id = resp.json()["id"]
        await client.post(f"/api/requests/{req_id}/submit")
        resp = await client.post(f"/api/cases/{req_id}/convert")
        case_id = resp.json()["id"]
        resp = await client.post(f"/api/cases/{case_id}/plan")
        plan_id = resp.json()["id"]
        resp = await client.post(f"/api/cases/{case_id}/runs", json={"plan_id": plan_id})
        run_id = resp.json()["id"]
        return run_id

    async def test_get_audit_trail_via_api(self, client):
        run_id = await self._run_full_flow(client)
        resp = await client.get(f"/api/runs/{run_id}/audit")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1  # At least run.created event

    async def test_get_evidence_empty(self, client):
        run_id = await self._run_full_flow(client)
        resp = await client.get(f"/api/runs/{run_id}/evidence")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_replay_bundle_not_found(self, client):
        resp = await client.get("/api/runs/nonexistent/replay-bundle")
        assert resp.status_code == 404
