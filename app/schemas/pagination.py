"""Shared pagination schema for list endpoints."""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    offset: int
    limit: int
    has_more: bool
