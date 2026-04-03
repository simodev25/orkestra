"""Audit schemas."""

from datetime import datetime
from typing import Optional, Any
from app.schemas.common import OrkBaseSchema


class AuditEventOut(OrkBaseSchema):
    id: str
    run_id: Optional[str]
    event_type: str
    actor_type: str
    actor_ref: str
    payload: Optional[dict[str, Any]]
    timestamp: datetime
    created_at: datetime


class EvidenceRecordOut(OrkBaseSchema):
    id: str
    run_id: str
    source_type: str
    source_ref: str
    linked_entity_type: Optional[str]
    linked_entity_ref: Optional[str]
    evidence_strength: Optional[str]
    summary: Optional[str]
    created_at: datetime


class ReplayBundleOut(OrkBaseSchema):
    id: str
    run_id: str
    bundle_status: str
    storage_ref: Optional[str]
    generated_by: Optional[str]
    replayable: bool
    replay_notes: Optional[str]
    created_at: datetime
