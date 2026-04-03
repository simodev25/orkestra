"""Case entity — the actionable business object."""

from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, new_id
from app.models.enums import CaseStatus, Criticality


class Case(BaseModel):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: new_id("case_"))
    request_id: Mapped[str] = mapped_column(String(36))
    tenant_id: Mapped[str] = mapped_column(String(36), default="default")
    case_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), default=Criticality.MEDIUM)
    status: Mapped[str] = mapped_column(String(30), default=CaseStatus.CREATED)
    current_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
