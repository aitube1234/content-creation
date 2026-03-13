"""Pagination and filtering utilities."""

from typing import Literal

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at")
    sort_order: Literal["asc", "desc"] = Field(default="desc")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class InputHistoryFilters(BaseModel):
    """Optional filters for input history list queries."""

    input_type: str | None = None
    workflow_state: str | None = None
