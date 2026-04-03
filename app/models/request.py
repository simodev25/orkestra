"""Request entity — entry point into the platform."""

from sqlalchemy import String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id
from app.models.enums import RequestStatus, Criticality, InputMode


class Request(BaseModel):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("req_"))
    tenant_id: Mapped[str] = mapped_column(String(36), default="default")
    created_by: Mapped[str] = mapped_column(String(100), default="system")
    title: Mapped[str] = mapped_column(String(255))
    request_text: Mapped[str] = mapped_column(Text)
    use_case: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workflow_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), default=Criticality.MEDIUM)
    input_mode: Mapped[str] = mapped_column(String(20), default=InputMode.MANUAL)
    status: Mapped[str] = mapped_column(String(30), default=RequestStatus.DRAFT)
    attachments_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
