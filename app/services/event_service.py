"""Event emission service — records AuditEvents."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)


async def emit_event(
    db: AsyncSession,
    event_type: str,
    actor_type: str,
    actor_ref: str,
    run_id: str | None = None,
    payload: dict | None = None,
):
    event = AuditEvent(
        event_type=event_type,
        actor_type=actor_type,
        actor_ref=actor_ref,
        run_id=run_id,
        payload=payload or {},
        timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    logger.info(f"Event emitted: {event_type} by {actor_type}/{actor_ref}")
