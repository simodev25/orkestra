"""Case API schemas."""

from datetime import datetime
from typing import Optional

from app.schemas.common import OrkBaseSchema


class CaseOut(OrkBaseSchema):
    id: str
    request_id: str
    case_type: Optional[str]
    business_context: Optional[str]
    criticality: str
    status: str
    current_run_id: Optional[str]
    document_count: int
    created_at: datetime
    updated_at: datetime
