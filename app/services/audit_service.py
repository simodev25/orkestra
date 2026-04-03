"""Audit service — event persistence, evidence, replay bundles."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent, EvidenceRecord, ReplayBundle
from app.models.run import Run

logger = logging.getLogger(__name__)


async def get_audit_trail(db: AsyncSession, run_id: str) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.run_id == run_id
    ).order_by(AuditEvent.timestamp)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_evidence(
    db: AsyncSession, run_id: str, source_type: str, source_ref: str,
    linked_entity_type: str | None = None, linked_entity_ref: str | None = None,
    evidence_strength: str | None = None, summary: str | None = None,
) -> EvidenceRecord:
    ev = EvidenceRecord(
        run_id=run_id, source_type=source_type, source_ref=source_ref,
        linked_entity_type=linked_entity_type, linked_entity_ref=linked_entity_ref,
        evidence_strength=evidence_strength, summary=summary,
    )
    db.add(ev)
    await db.flush()
    return ev


async def get_evidence_for_run(db: AsyncSession, run_id: str) -> list[EvidenceRecord]:
    stmt = select(EvidenceRecord).where(EvidenceRecord.run_id == run_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def generate_replay_bundle(db: AsyncSession, run_id: str) -> ReplayBundle:
    run = await db.get(Run, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")
    if run.status not in ("completed", "failed", "blocked"):
        raise ValueError(f"Cannot generate replay bundle for run in state {run.status}")

    # Check if bundle already exists
    stmt = select(ReplayBundle).where(ReplayBundle.run_id == run_id)
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing and existing.bundle_status == "ready":
        return existing

    # Check audit trail completeness
    events = await get_audit_trail(db, run_id)

    bundle = ReplayBundle(
        run_id=run_id,
        bundle_status="ready" if len(events) > 0 else "failed",
        replayable=len(events) > 0,
        generated_by="audit_service",
        replay_notes=f"Bundle generated with {len(events)} audit events",
    )
    db.add(bundle)
    await db.flush()
    return bundle


async def get_replay_bundle(db: AsyncSession, run_id: str) -> ReplayBundle | None:
    stmt = select(ReplayBundle).where(ReplayBundle.run_id == run_id)
    result = await db.execute(stmt)
    return result.scalars().first()
