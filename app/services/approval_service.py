"""Approval service — human review workflow."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRequest
from app.models.run import Run
from app.models.enums import ApprovalStatus
from app.state_machines.approval_sm import ApprovalStateMachine
from app.state_machines.run_sm import RunStateMachine
from app.services.event_service import emit_event

logger = logging.getLogger(__name__)


async def create_approval(
    db: AsyncSession,
    run_id: str,
    case_id: str,
    approval_type: str,
    reason: str,
    reviewer_role: str | None = None,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        run_id=run_id,
        case_id=case_id,
        approval_type=approval_type,
        reason=reason,
        reviewer_role=reviewer_role,
        status=ApprovalStatus.REQUESTED,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(approval)
    await db.flush()
    await emit_event(db, "approval.requested", "system", "approval_service",
                     run_id=run_id, payload={"approval_id": approval.id, "type": approval_type})
    return approval


async def assign_reviewer(db: AsyncSession, approval_id: str, assigned_to: str) -> ApprovalRequest:
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise ValueError(f"Approval {approval_id} not found")

    sm = ApprovalStateMachine(approval.status)
    if not sm.transition("assigned"):
        raise ValueError(f"Cannot assign approval in state {approval.status}")
    approval.status = sm.state
    approval.assigned_to = assigned_to

    sm.transition("pending")
    approval.status = sm.state

    await db.flush()
    await emit_event(db, "approval.assigned", "system", "approval_service",
                     run_id=approval.run_id, payload={"approval_id": approval_id, "assigned_to": assigned_to})
    return approval


async def approve(db: AsyncSession, approval_id: str, comment: str = "") -> ApprovalRequest:
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise ValueError(f"Approval {approval_id} not found")

    sm = ApprovalStateMachine(approval.status)
    if not sm.transition("approved"):
        raise ValueError(f"Cannot approve in state {approval.status}")
    approval.status = sm.state
    approval.decision_comment = comment
    approval.resolved_at = datetime.now(timezone.utc)

    # Resume run if it was waiting
    run = await db.get(Run, approval.run_id)
    if run and run.status == "waiting_review":
        run_sm = RunStateMachine(run.status)
        run_sm.transition("running")
        run.status = run_sm.state

    await db.flush()
    await emit_event(db, "approval.approved", "human", "approval_service",
                     run_id=approval.run_id, payload={"approval_id": approval_id})
    return approval


async def reject(db: AsyncSession, approval_id: str, comment: str = "") -> ApprovalRequest:
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise ValueError(f"Approval {approval_id} not found")

    sm = ApprovalStateMachine(approval.status)
    if not sm.transition("rejected"):
        raise ValueError(f"Cannot reject in state {approval.status}")
    approval.status = sm.state
    approval.decision_comment = comment
    approval.resolved_at = datetime.now(timezone.utc)

    # Block run
    run = await db.get(Run, approval.run_id)
    if run and run.status == "waiting_review":
        run_sm = RunStateMachine(run.status)
        run_sm.transition("blocked")
        run.status = run_sm.state

    await db.flush()
    await emit_event(db, "approval.rejected", "human", "approval_service",
                     run_id=approval.run_id, payload={"approval_id": approval_id})
    return approval


async def request_refinement(db: AsyncSession, approval_id: str, comment: str = "") -> ApprovalRequest:
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise ValueError(f"Approval {approval_id} not found")

    sm = ApprovalStateMachine(approval.status)
    if not sm.transition("refine_required"):
        raise ValueError(f"Cannot request refinement in state {approval.status}")
    approval.status = sm.state
    approval.decision_comment = comment
    approval.resolved_at = datetime.now(timezone.utc)

    await db.flush()
    await emit_event(db, "approval.refine_required", "human", "approval_service",
                     run_id=approval.run_id, payload={"approval_id": approval_id})
    return approval


async def list_approvals(
    db: AsyncSession, status: str | None = None, run_id: str | None = None,
    limit: int = 50, offset: int = 0,
) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    if run_id:
        stmt = stmt.where(ApprovalRequest.run_id == run_id)
    stmt = stmt.order_by(ApprovalRequest.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_approval(db: AsyncSession, approval_id: str) -> ApprovalRequest | None:
    return await db.get(ApprovalRequest, approval_id)
