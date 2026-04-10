"""Case service — handles case lifecycle and request conversion."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import Request
from app.models.case import Case
from app.models.enums import CaseStatus
from app.state_machines.request_sm import RequestStateMachine
from app.state_machines.case_sm import CaseStateMachine
from app.services.event_service import emit_event
from app.services.base_service import paginated_list


async def convert_request_to_case(db: AsyncSession, request_id: str) -> Case:
    req = await db.get(Request, request_id)
    if not req:
        raise ValueError(f"Request {request_id} not found")

    if req.status == "submitted":
        sm = RequestStateMachine(req.status)
        sm.transition("accepted")
        req.status = sm.state

    sm = RequestStateMachine(req.status)
    if not sm.transition("converted_to_case"):
        raise ValueError(f"Cannot convert request in state {req.status}")
    req.status = sm.state

    case = Case(
        request_id=req.id,
        tenant_id=req.tenant_id,
        case_type=req.use_case,
        criticality=req.criticality,
        status=CaseStatus.CREATED,
        document_count=req.attachments_count,
    )
    db.add(case)
    await db.flush()

    case_sm = CaseStateMachine(case.status)
    case_sm.transition("ready_for_planning")
    case.status = case_sm.state

    await emit_event(db, "request.converted_to_case", "system", "case_service",
                     payload={"request_id": req.id, "case_id": case.id})
    return case


async def list_cases(
    db: AsyncSession,
    status: str | None = None,
    criticality: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Case]:
    filters = []
    if status:
        filters.append(Case.status == status)
    if criticality:
        filters.append(Case.criticality == criticality)
    items, _ = await paginated_list(db, Case, filters=filters, limit=limit, offset=offset)
    return items


async def get_case(db: AsyncSession, case_id: str) -> Case | None:
    return await db.get(Case, case_id)
