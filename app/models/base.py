"""Base model with common fields."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_id(prefix: str = ""):
    """Generate a prefixed UUID that fits in VARCHAR(36).

    Uses 24 hex chars (96 bits entropy) to leave room for prefixes up to 12 chars.
    Collision probability is negligible (birthday bound ~2^48 = 280 trillion records).
    """
    uid = uuid.uuid4().hex[:24]
    return f"{prefix}{uid}" if prefix else str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class BaseModel(Base, TimestampMixin):
    __abstract__ = True
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
