"""Pydantic v2 request/response schemas for draft content item creation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    ContributionStatus,
    CreationSource,
    MetadataEngineWriteStatus,
    ReportStatus,
    VersionEventType,
)


# --- Request schemas ---


class CreateDraftContentItemRequest(BaseModel):
    """Schema for creating a new draft content item."""

    creation_source: CreationSource
    lead_creator_account_id: uuid.UUID
    video_draft_url: str = Field(..., min_length=1)
    pipeline_job_reference: str | None = None


class MetadataOverrideRequest(BaseModel):
    """Schema for overriding metadata fields on a draft content item."""

    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    topic_cluster: str | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "MetadataOverrideRequest":
        if not any([self.title, self.description, self.tags, self.topic_cluster]):
            raise ValueError("At least one metadata field must be provided for override.")
        return self


class ThumbnailSelectRequest(BaseModel):
    """Schema for selecting a thumbnail."""

    thumbnail_id: uuid.UUID


# --- Response schemas ---


class ErrorResponse(BaseModel):
    """Consistent error response format."""

    error_code: str
    message: str
    details: dict | None = None


class DraftContentItemResponse(BaseModel):
    """Full representation of a draft content item."""

    model_config = ConfigDict(from_attributes=True)

    content_item_id: uuid.UUID
    lead_creator_account_id: uuid.UUID
    lifecycle_state: LifecycleState
    creation_source: CreationSource
    video_draft_url: str | None
    metadata_status: MetadataStatus
    selected_thumbnail_id: uuid.UUID | None
    originality_report_id: uuid.UUID | None
    pipeline_job_reference: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def lifecycle_state_label(self) -> str:
        return self.lifecycle_state.value

    @property
    def metadata_status_label(self) -> str:
        return self.metadata_status.value


class DraftContentItemSummaryResponse(BaseModel):
    """Abbreviated representation for list views."""

    model_config = ConfigDict(from_attributes=True)

    content_item_id: uuid.UUID
    lead_creator_account_id: uuid.UUID
    lifecycle_state: LifecycleState
    creation_source: CreationSource
    metadata_status: MetadataStatus
    selected_thumbnail_id: uuid.UUID | None
    lifecycle_state_label: str = ""
    metadata_status_label: str = ""
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def compute_labels(self) -> "DraftContentItemSummaryResponse":
        self.lifecycle_state_label = self.lifecycle_state.value
        self.metadata_status_label = self.metadata_status.value
        return self


class DraftContentItemListResponse(BaseModel):
    """Paginated list of draft content item summaries."""

    items: list[DraftContentItemSummaryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class MetadataResponse(BaseModel):
    """Full representation of an AI-generated metadata record."""

    model_config = ConfigDict(from_attributes=True)

    metadata_id: uuid.UUID
    content_item_id: uuid.UUID
    ai_title_suggestion: str | None
    ai_description: str | None
    ai_topic_tags: list[str] | None
    ai_topic_cluster: str | None
    creator_override_title: str | None
    creator_override_description: str | None
    creator_override_tags: list[str] | None
    metadata_engine_write_status: MetadataEngineWriteStatus
    created_at: datetime


class ThumbnailResponse(BaseModel):
    """Representation of an AI-generated thumbnail option."""

    model_config = ConfigDict(from_attributes=True)

    thumbnail_id: uuid.UUID
    content_item_id: uuid.UUID
    thumbnail_url: str
    display_order: int
    is_selected: bool
    created_at: datetime


class VersionHistoryEntryResponse(BaseModel):
    """Representation of a version history entry."""

    model_config = ConfigDict(from_attributes=True)

    version_entry_id: uuid.UUID
    content_item_id: uuid.UUID
    event_type: VersionEventType
    actor_account_id: uuid.UUID
    actor_role: ActorRole
    event_payload: dict | None
    contribution_status: ContributionStatus | None
    created_at: datetime


class VersionHistoryListResponse(BaseModel):
    """Paginated list of version history entries."""

    items: list[VersionHistoryEntryResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class OriginalityReportResponse(BaseModel):
    """Representation of an originality report."""

    model_config = ConfigDict(from_attributes=True)

    originality_report_id: uuid.UUID
    content_item_id: uuid.UUID
    creator_account_id: uuid.UUID
    duplicate_risk_score: int
    similar_content_items: list[str] | None
    differentiation_recommendations: list[str] | None
    report_status: ReportStatus
    created_at: datetime


class PrePublishTransitionResponse(BaseModel):
    """Response for pre-publish transition initiation."""

    status: str  # checking_originality | awaiting_confirmation | timeout
    originality_report: OriginalityReportResponse | None = None
