"""Tests for app.services.base_service."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.enums import CaseStatus
from app.services.base_service import paginated_list


@pytest.mark.asyncio
async def test_paginated_list_empty(db_session: AsyncSession):
    items, total = await paginated_list(db_session, Case)
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_paginated_list_with_data(db_session: AsyncSession):
    c1 = Case(id="c1", request_id="req_test", case_type="t", status=CaseStatus.CREATED, criticality="low")
    c2 = Case(id="c2", request_id="req_test", case_type="t", status=CaseStatus.CREATED, criticality="high")
    db_session.add_all([c1, c2])
    await db_session.flush()

    items, total = await paginated_list(db_session, Case, limit=1, offset=0)
    assert total == 2
    assert len(items) == 1


@pytest.mark.asyncio
async def test_paginated_list_with_filters(db_session: AsyncSession):
    c1 = Case(id="c1", request_id="req_test", case_type="t", status=CaseStatus.CREATED, criticality="low")
    c2 = Case(id="c2", request_id="req_test", case_type="t", status="completed", criticality="high")
    db_session.add_all([c1, c2])
    await db_session.flush()

    items, total = await paginated_list(
        db_session, Case,
        filters=[Case.status == CaseStatus.CREATED]
    )
    assert total == 1
    assert items[0].id == "c1"
