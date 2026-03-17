"""Pydantic v2 request/response schemas for script prompt ingestion."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
    WorkflowState,
)


class CreateInputRequest(BaseModel):
    """Schema for creating a new Draft input record."""

    content_text: str = Field(..., min_length=1)
    creator_id: uuid.UUID
    input_type: InputType | None = None


class UpdateInputRequest(BaseModel):
    """Schema for updating a Draft input record (partial update)."""

    content_text: str | None = None
    input_type: InputType | None = None


class ValidationErrorDetail(BaseModel):
    """Structured validation error detail."""

    field: str
    message: str
    error_code: str


class InputRecordResponse(BaseModel):
    """Full representation of a persisted input record."""

    model_config = ConfigDict(from_attributes=True)

    input_record_id: uuid.UUID
    creator_id: uuid.UUID
    input_type: InputType | None
    content_text: str
    workflow_state: WorkflowState
    validation_errors: list[str] | None
    generation_request_id: uuid.UUID | None
    created_at: datetime
    last_modified_at: datetime
    submitted_at: datetime | None
    character_count: int


class InputRecordSummaryResponse(BaseModel):
    """Abbreviated representation for history list."""

    model_config = ConfigDict(from_attributes=True)

    input_record_id: uuid.UUID
    input_type: InputType | None
    workflow_state: WorkflowState
    created_at: datetime
    last_modified_at: datetime
    character_count: int


class PaginatedInputHistoryResponse(BaseModel):
    """Paginated list of input record summaries."""

    items: list[InputRecordSummaryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class GenerationInitiatedResponse(BaseModel):
    """Response when generation is successfully initiated."""

    input_record_id: uuid.UUID
    generation_request_id: uuid.UUID
    workflow_state: WorkflowState
    message: str = "Video generation has been initiated successfully."
