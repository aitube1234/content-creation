"""Pydantic v2 request/response schemas for AI video draft assembly."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    LifecycleState,
    MetadataStatus,
)


# --- Embedded types ---


class SceneSchema(BaseModel):
    """Schema for a single scene within a video draft."""

    scene_id: uuid.UUID
    pacing_value: float = Field(ge=0.1, le=10.0)
    visual_asset_id: uuid.UUID
    voice_segment_id: uuid.UUID


class VersionEntrySchema(BaseModel):
    """Schema for a single version history entry."""

    version_id: uuid.UUID
    change_type: str
    changed_fields: dict
    changed_at: datetime
    changed_by: uuid.UUID


# --- Request schemas ---


class CreateAssemblyRequest(BaseModel):
    """Schema for submitting a new video draft assembly."""

    input_type: ContentInputType
    input_text: str = Field(..., min_length=1)

    @field_validator("input_text")
    @classmethod
    def validate_input_text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Input text must not be blank.")
        return v


class SceneEditPacingRequest(BaseModel):
    """Schema for adjusting scene pacing."""

    pacing_value: float = Field(..., ge=0.1, le=10.0)


class SceneEditVisualRequest(BaseModel):
    """Schema for swapping a scene visual."""

    visual_asset_id: uuid.UUID


class SceneEditVoiceRequest(BaseModel):
    """Schema for re-recording scene voice."""

    voice_segment_url: str = Field(..., min_length=1)


class MetadataFieldUpdateRequest(BaseModel):
    """Schema for updating a single metadata field."""

    value: str = Field(..., min_length=1)


class MetadataTagsUpdateRequest(BaseModel):
    """Schema for updating metadata tags."""

    tags: list[str] = Field(..., min_length=1)


class ThumbnailSelectionRequest(BaseModel):
    """Schema for selecting a thumbnail."""

    selected_thumbnail_url: str = Field(..., min_length=1)


class RetryAssemblyRequest(BaseModel):
    """Schema for retrying a failed assembly."""

    pass


# --- Validation ---


class ValidationErrorDetail(BaseModel):
    """Structured validation error detail."""

    field: str
    message: str
    error_code: str


# --- Response schemas ---


class ContentItemResponse(BaseModel):
    """Full representation of a content item."""

    model_config = ConfigDict(from_attributes=True)

    content_item_id: uuid.UUID
    creator_id: uuid.UUID
    input_type: ContentInputType
    input_text: str
    input_locale: str | None
    lifecycle_state: LifecycleState
    assembly_status: AssemblyStatus
    video_draft_url: str | None
    scenes: list[dict] | None
    metadata_status: MetadataStatus | None
    ai_title: str | None
    ai_description: str | None
    ai_tags: list[str] | None
    ai_topic_cluster: str | None
    thumbnail_options: list[str] | None
    selected_thumbnail_url: str | None
    version_history: list[dict] | None
    word_count: int
    created_at: datetime
    updated_at: datetime


class ContentItemSummaryResponse(BaseModel):
    """Abbreviated representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    content_item_id: uuid.UUID
    input_type: ContentInputType
    lifecycle_state: LifecycleState
    assembly_status: AssemblyStatus
    metadata_status: MetadataStatus | None
    ai_title: str | None
    selected_thumbnail_url: str | None
    word_count: int
    created_at: datetime
    updated_at: datetime


class PaginatedContentItemResponse(BaseModel):
    """Paginated list of content item summaries."""

    items: list[ContentItemSummaryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class AssemblyInitiatedResponse(BaseModel):
    """Response when assembly is submitted or retried."""

    content_item_id: uuid.UUID
    assembly_status: AssemblyStatus
    message: str = "Video draft assembly has been initiated."


class VersionHistoryResponse(BaseModel):
    """Response for version history endpoint."""

    content_item_id: uuid.UUID
    versions: list[dict]


class SSEEventSchema(BaseModel):
    """Schema for SSE status events."""

    event_type: str
    content_item_id: uuid.UUID
    run_id: str
    thread_id: str
    assembly_status: AssemblyStatus | None = None
    progress: float | None = None
    message: str | None = None


class EnvelopeResponse(BaseModel):
    """Standard envelope response format."""

    data: dict | list | None = None
    meta: dict | None = None
    errors: list[dict] | None = None
