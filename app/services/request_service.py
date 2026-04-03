"""Request service — handles request lifecycle."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Request
from app.models.enums import RequestStatus
from app.schemas.request import RequestCreate
from app.state_machines.request_sm import RequestStateMachine
from app.services.event_service import emit_event


async def create_request(db: AsyncSession, data: RequestCreate) -> Request:
    req = Request(
        title=data.title,
        request_text=data.request_text,
        use_case=data.use_case,
        workflow_template_id=data.workflow_template_id,
        criticality=data.criticality,
        status=RequestStatus.DRAFT,
    )
    db.add(req)
    await db.flush()
    await emit_event(db, "request.created", "system", "request_service", payload={"request_id": req.id})
    return req


async def submit_request(db: AsyncSession, request_id: str) -> Request:
    req = await db.get(Request, request_id)
    if not req:
        raise ValueError(f"Request {request_id} not found")
    sm = RequestStateMachine(req.status)
    if not sm.transition("submitted"):
        raise ValueError(f"Cannot submit request in state {req.status}")
    req.status = sm.state
    await emit_event(db, "request.submitted", "system", "request_service", payload={"request_id": req.id})
    return req


async def list_requests(
    db: AsyncSession,
    status: str | None = None,
    criticality: str | None = None,
    use_case: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Request]:
    stmt = select(Request)
    if status:
        stmt = stmt.where(Request.status == status)
    if criticality:
        stmt = stmt.where(Request.criticality == criticality)
    if use_case:
        stmt = stmt.where(Request.use_case == use_case)
    stmt = stmt.order_by(Request.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_request(db: AsyncSession, request_id: str) -> Request | None:
    return await db.get(Request, request_id)
