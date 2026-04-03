"""AuditEvent, EvidenceRecord, ReplayBundle entities."""

from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id, utcnow


class AuditEvent(BaseModel):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("evt_"))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    actor_type: Mapped[str] = mapped_column(String(50))
    actor_ref: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[str] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvidenceRecord(BaseModel):
    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("ev_"))
    run_id: Mapped[str] = mapped_column(String(36))
    source_type: Mapped[str] = mapped_column(String(50))
    source_ref: Mapped[str] = mapped_column(String(100))
    linked_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linked_entity_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_strength: Mapped[str | None] = mapped_column(String(20), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReplayBundle(BaseModel):
    __tablename__ = "replay_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("rb_"))
    run_id: Mapped[str] = mapped_column(String(36))
    bundle_status: Mapped[str] = mapped_column(String(30), default="not_generated")
    storage_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replayable: Mapped[bool] = mapped_column(Boolean, default=False)
    replay_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
