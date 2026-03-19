"""FastAPI router for draft content item creation endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.database import get_async_session
from backend.services.content_creation.utils.auth import get_current_creator_id
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.draft_creation_service import (
    DraftCreationService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.draft_lifecycle_service import (
    DraftLifecycleService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.draft_query_service import (
    DraftQueryService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    CreationSource,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.metadata_service import (
    MetadataService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.schemas import (
    CreateDraftContentItemRequest,
    DraftContentItemListResponse,
    DraftContentItemResponse,
    DraftContentItemSummaryResponse,
    MetadataOverrideRequest,
    MetadataResponse,
    OriginalityReportResponse,
    PrePublishTransitionResponse,
    ThumbnailResponse,
    ThumbnailSelectRequest,
    VersionHistoryEntryResponse,
    VersionHistoryListResponse,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.thumbnail_service import (
    ThumbnailService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.version_history_service import (
    VersionHistoryService,
)

router = APIRouter(
    prefix="/v1/draft-content-items",
    tags=["Draft Content Items"],
)


# --- Dependency factories ---


def get_draft_creation_service() -> DraftCreationService:
    """Dependency that provides the draft creation service instance."""
    return DraftCreationService()


def get_draft_query_service() -> DraftQueryService:
    """Dependency that provides the draft query service instance."""
    return DraftQueryService()


def get_draft_lifecycle_service() -> DraftLifecycleService:
    """Dependency that provides the draft lifecycle service instance."""
    return DraftLifecycleService()


def get_metadata_service() -> MetadataService:
    """Dependency that provides the metadata service instance."""
    return MetadataService()


def get_thumbnail_service() -> ThumbnailService:
    """Dependency that provides the thumbnail service instance."""
    return ThumbnailService()


def get_version_history_service() -> VersionHistoryService:
    """Dependency that provides the version history service instance."""
    return VersionHistoryService()


# --- Draft content item CRUD endpoints ---


@router.post(
    "",
    response_model=DraftContentItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft_content_item(
    body: CreateDraftContentItemRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftCreationService, Depends(get_draft_creation_service)],
) -> DraftContentItemResponse:
    """Create a Draft Content Item from pipeline completion or workspace save."""
    record = await service.create_draft(
        session,
        lead_creator_account_id=body.lead_creator_account_id,
        creation_source=body.creation_source,
        video_draft_url=body.video_draft_url,
        pipeline_job_reference=body.pipeline_job_reference,
    )
    return DraftContentItemResponse.model_validate(record)


@router.get(
    "",
    response_model=DraftContentItemListResponse,
)
async def list_draft_content_items(
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftQueryService, Depends(get_draft_query_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    lifecycle_state: LifecycleState | None = Query(default=None),
    metadata_status: MetadataStatus | None = Query(default=None),
    creation_source: CreationSource | None = Query(default=None),
) -> DraftContentItemListResponse:
    """List all Draft Content Items for the authenticated creator."""
    records, total = await service.list_draft_content_items(
        session,
        creator_id=creator_id,
        lifecycle_state=lifecycle_state,
        metadata_status=metadata_status,
        creation_source=creation_source,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    items = [DraftContentItemSummaryResponse.model_validate(r) for r in records]
    return DraftContentItemListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_previous=page > 1,
    )


@router.get(
    "/{content_item_id}",
    response_model=DraftContentItemResponse,
)
async def get_draft_content_item(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftQueryService, Depends(get_draft_query_service)],
) -> DraftContentItemResponse:
    """Retrieve a single Draft Content Item in full."""
    record = await service.get_draft_content_item(session, content_item_id, creator_id)
    return DraftContentItemResponse.model_validate(record)


@router.delete(
    "/{content_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_draft_content_item(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftCreationService, Depends(get_draft_creation_service)],
) -> None:
    """Delete a Draft Content Item (only when lifecycle_state = Draft)."""
    await service.delete_draft(session, content_item_id, creator_id)


# --- Metadata endpoints ---


@router.get(
    "/{content_item_id}/metadata",
    response_model=MetadataResponse,
)
async def get_metadata(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[MetadataService, Depends(get_metadata_service)],
) -> MetadataResponse:
    """Retrieve the AI-generated metadata for a Draft Content Item."""
    metadata = await service.get_metadata(session, content_item_id, creator_id)
    return MetadataResponse.model_validate(metadata)


@router.patch(
    "/{content_item_id}/metadata",
    response_model=MetadataResponse,
)
async def override_metadata(
    content_item_id: uuid.UUID,
    body: MetadataOverrideRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[MetadataService, Depends(get_metadata_service)],
) -> MetadataResponse:
    """Override metadata fields on a Draft Content Item."""
    metadata = await service.override_metadata(
        session,
        content_item_id,
        creator_id,
        title=body.title,
        description=body.description,
        tags=body.tags,
        topic_cluster=body.topic_cluster,
    )
    return MetadataResponse.model_validate(metadata)


# --- Thumbnail endpoints ---


@router.get(
    "/{content_item_id}/thumbnails",
    response_model=list[ThumbnailResponse],
)
async def get_thumbnails(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ThumbnailService, Depends(get_thumbnail_service)],
) -> list[ThumbnailResponse]:
    """Retrieve all AI-generated thumbnail options for a Draft Content Item."""
    thumbnails = await service.get_thumbnails(session, content_item_id, creator_id)
    return [ThumbnailResponse.model_validate(t) for t in thumbnails]


@router.patch(
    "/{content_item_id}/thumbnails/select",
    response_model=ThumbnailResponse,
)
async def select_thumbnail(
    content_item_id: uuid.UUID,
    body: ThumbnailSelectRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ThumbnailService, Depends(get_thumbnail_service)],
) -> ThumbnailResponse:
    """Select a thumbnail by thumbnail_id."""
    thumbnail = await service.select_thumbnail(
        session, content_item_id, creator_id, body.thumbnail_id,
    )
    return ThumbnailResponse.model_validate(thumbnail)


# --- Version history endpoints ---


@router.get(
    "/{content_item_id}/version-history",
    response_model=VersionHistoryListResponse,
)
async def get_version_history(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[VersionHistoryService, Depends(get_version_history_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> VersionHistoryListResponse:
    """Retrieve version history entries for a Draft Content Item."""
    entries, total = await service.list_entries(
        session,
        content_item_id,
        requester_id=creator_id,
        page=page,
        page_size=page_size,
        sort_order=sort_order,
    )
    items = [VersionHistoryEntryResponse.model_validate(e) for e in entries]
    return VersionHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_previous=page > 1,
    )


@router.patch(
    "/{content_item_id}/version-history/{version_entry_id}/accept",
    response_model=VersionHistoryEntryResponse,
)
async def accept_contribution(
    content_item_id: uuid.UUID,
    version_entry_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[VersionHistoryService, Depends(get_version_history_service)],
) -> VersionHistoryEntryResponse:
    """Lead creator accepts a contributor contribution."""
    entry = await service.accept_contribution(
        session, content_item_id, version_entry_id, creator_id,
    )
    return VersionHistoryEntryResponse.model_validate(entry)


@router.patch(
    "/{content_item_id}/version-history/{version_entry_id}/override",
    response_model=VersionHistoryEntryResponse,
)
async def override_contribution(
    content_item_id: uuid.UUID,
    version_entry_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[VersionHistoryService, Depends(get_version_history_service)],
) -> VersionHistoryEntryResponse:
    """Lead creator overrides a contributor contribution."""
    entry = await service.override_contribution(
        session, content_item_id, version_entry_id, creator_id,
    )
    return VersionHistoryEntryResponse.model_validate(entry)


# --- Lifecycle transition endpoints ---


@router.post(
    "/{content_item_id}/transition/pre-publish",
    response_model=PrePublishTransitionResponse,
)
async def initiate_pre_publish_transition(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftLifecycleService, Depends(get_draft_lifecycle_service)],
) -> PrePublishTransitionResponse:
    """Initiate Draft-to-Pre-Publish transition with originality check."""
    transition_status, report = await service.initiate_pre_publish_transition(
        session, content_item_id, creator_id,
    )
    report_response = OriginalityReportResponse.model_validate(report) if report else None
    return PrePublishTransitionResponse(
        status=transition_status,
        originality_report=report_response,
    )


@router.post(
    "/{content_item_id}/transition/pre-publish/confirm",
    response_model=DraftContentItemResponse,
)
async def confirm_pre_publish(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftLifecycleService, Depends(get_draft_lifecycle_service)],
) -> DraftContentItemResponse:
    """Confirm Pre-Publish transition after reviewing originality report."""
    record = await service.confirm_pre_publish(session, content_item_id, creator_id)
    return DraftContentItemResponse.model_validate(record)


@router.post(
    "/{content_item_id}/transition/pre-publish/retry-originality",
    response_model=PrePublishTransitionResponse,
)
async def retry_originality_check(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[DraftLifecycleService, Depends(get_draft_lifecycle_service)],
) -> PrePublishTransitionResponse:
    """Retry originality check after timeout."""
    transition_status, report = await service.retry_originality(
        session, content_item_id, creator_id,
    )
    report_response = OriginalityReportResponse.model_validate(report) if report else None
    return PrePublishTransitionResponse(
        status=transition_status,
        originality_report=report_response,
    )
