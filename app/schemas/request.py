"""Request API schemas."""

from pydantic import Field
from datetime import datetime
from typing import Optional

from app.schemas.common import OrkBaseSchema


class RequestCreate(OrkBaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    request_text: str = Field(..., min_length=1)
    use_case: Optional[str] = None
    workflow_template_id: Optional[str] = None
    criticality: str = "medium"


class RequestOut(OrkBaseSchema):
    id: str
    title: str
    request_text: str
    use_case: Optional[str]
    workflow_template_id: Optional[str]
    criticality: str
    input_mode: str
    status: str
    attachments_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime
