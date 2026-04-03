"""Shared schema components."""

from pydantic import BaseModel


class OrkBaseSchema(BaseModel):
    model_config = {"from_attributes": True}
