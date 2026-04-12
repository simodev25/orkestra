"""Generic query helpers shared across services."""

from __future__ import annotations

from typing import Any, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

M = TypeVar("M", bound=DeclarativeBase)


async def paginated_list(
    db: AsyncSession,
    model: Type[M],
    filters: list[Any] | None = None,
    order_by: Any = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[M], int]:
    """Execute a paginated SELECT and return (items, total_count).

    Args:
        db: Async SQLAlchemy session.
        model: ORM model class to query.
        filters: List of SQLAlchemy column expressions to WHERE-chain.
        order_by: Column expression for ORDER BY (defaults to model.created_at desc
                  if the attribute exists, otherwise no ordering).
        limit: Maximum rows to return.
        offset: Number of rows to skip.

    Returns:
        Tuple of (list of model instances, total row count ignoring limit/offset).
    """
    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)

    for f in (filters or []):
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    if order_by is not None:
        stmt = stmt.order_by(order_by)
    elif hasattr(model, "created_at"):
        stmt = stmt.order_by(model.created_at.desc())

    stmt = stmt.limit(limit).offset(offset)

    items_result = await db.execute(stmt)
    total = await db.scalar(count_stmt) or 0

    return list(items_result.scalars().all()), total
