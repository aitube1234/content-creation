"""FastAPI router for AI video draft assembly endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.database import get_async_session
from backend.services.content_creation.utils.auth import get_current_creator_id
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.metadata_service import (
    MetadataService,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.scene_edit_service import (
    SceneEditService,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.schemas import (
    AssemblyInitiatedResponse,
    ContentItemResponse,
    ContentItemSummaryResponse,
    CreateAssemblyRequest,
    MetadataFieldUpdateRequest,
    MetadataTagsUpdateRequest,
    PaginatedContentItemResponse,
    SceneEditPacingRequest,
    SceneEditVisualRequest,
    SceneEditVoiceRequest,
    ThumbnailSelectionRequest,
    VersionHistoryResponse,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.service import (
    AssemblyService,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.streaming import (
    generate_assembly_events,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.thumbnail_service import (
    ThumbnailService,
)

router = APIRouter(
    prefix="/v1/video-draft-assembly",
    tags=["AI Video Draft Assembly"],
)


def get_assembly_service() -> AssemblyService:
    """Dependency that provides the assembly service instance."""
    return AssemblyService()


def get_scene_edit_service() -> SceneEditService:
    """Dependency that provides the scene edit service instance."""
    return SceneEditService()


def get_metadata_service() -> MetadataService:
    """Dependency that provides the metadata service instance."""
    return MetadataService()


def get_thumbnail_service() -> ThumbnailService:
    """Dependency that provides the thumbnail service instance."""
    return ThumbnailService()


# --- Assembly endpoints ---


@router.post(
    "",
    response_model=ContentItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_assembly(
    body: CreateAssemblyRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[AssemblyService, Depends(get_assembly_service)],
) -> ContentItemResponse:
    """Submit a new video draft assembly request."""
    record = await service.submit_assembly(
        session,
        creator_id=creator_id,
        input_type=body.input_type,
        input_text=body.input_text,
    )
    return ContentItemResponse.model_validate(record)


@router.get(
    "",
    response_model=PaginatedContentItemResponse,
)
async def list_content_items(
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[AssemblyService, Depends(get_assembly_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    lifecycle_state: LifecycleState | None = Query(default=None),
    assembly_status: AssemblyStatus | None = Query(default=None),
    metadata_status: MetadataStatus | None = Query(default=None),
) -> PaginatedContentItemResponse:
    """List content items with pagination, filtering, and sorting."""
    records, total = await service.list_content_items(
        session,
        creator_id=creator_id,
        lifecycle_state=lifecycle_state,
        assembly_status=assembly_status,
        metadata_status=metadata_status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    items = [ContentItemSummaryResponse.model_validate(r) for r in records]
    return PaginatedContentItemResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_previous=page > 1,
    )


@router.get(
    "/{content_item_id}",
    response_model=ContentItemResponse,
)
async def get_content_item(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[AssemblyService, Depends(get_assembly_service)],
) -> ContentItemResponse:
    """Retrieve a single content item in full."""
    record = await service.get_content_item(session, content_item_id, creator_id)
    return ContentItemResponse.model_validate(record)


@router.post(
    "/{content_item_id}/retry",
    response_model=AssemblyInitiatedResponse,
)
async def retry_assembly(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[AssemblyService, Depends(get_assembly_service)],
) -> AssemblyInitiatedResponse:
    """Retry a failed assembly."""
    record = await service.retry_assembly(session, content_item_id, creator_id)
    return AssemblyInitiatedResponse(
        content_item_id=record.content_item_id,
        assembly_status=record.assembly_status,
        message="Video draft assembly retry has been initiated.",
    )


# --- Scene editing endpoints ---


@router.patch(
    "/{content_item_id}/scenes/{scene_id}/pacing",
    response_model=ContentItemResponse,
)
async def update_scene_pacing(
    content_item_id: uuid.UUID,
    scene_id: str,
    body: SceneEditPacingRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[SceneEditService, Depends(get_scene_edit_service)],
) -> ContentItemResponse:
    """Adjust pacing for a specific scene."""
    record = await service.update_pacing(
        session, content_item_id, creator_id, scene_id, body.pacing_value
    )
    return ContentItemResponse.model_validate(record)


@router.patch(
    "/{content_item_id}/scenes/{scene_id}/visual",
    response_model=ContentItemResponse,
)
async def swap_scene_visual(
    content_item_id: uuid.UUID,
    scene_id: str,
    body: SceneEditVisualRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[SceneEditService, Depends(get_scene_edit_service)],
) -> ContentItemResponse:
    """Swap the visual asset for a specific scene."""
    record = await service.swap_visual(
        session, content_item_id, creator_id, scene_id, str(body.visual_asset_id)
    )
    return ContentItemResponse.model_validate(record)


@router.post(
    "/{content_item_id}/scenes/{scene_id}/voice",
    response_model=ContentItemResponse,
)
async def re_record_scene_voice(
    content_item_id: uuid.UUID,
    scene_id: str,
    body: SceneEditVoiceRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[SceneEditService, Depends(get_scene_edit_service)],
) -> ContentItemResponse:
    """Re-record voice for a specific scene."""
    record = await service.re_record_voice(
        session, content_item_id, creator_id, scene_id, body.voice_segment_url
    )
    return ContentItemResponse.model_validate(record)


# --- Metadata endpoints ---


@router.patch(
    "/{content_item_id}/metadata/title",
    response_model=ContentItemResponse,
)
async def update_metadata_title(
    content_item_id: uuid.UUID,
    body: MetadataFieldUpdateRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[MetadataService, Depends(get_metadata_service)],
) -> ContentItemResponse:
    """Update the AI-generated title with creator override."""
    record = await service.update_title(
        session, content_item_id, creator_id, body.value
    )
    return ContentItemResponse.model_validate(record)


@router.patch(
    "/{content_item_id}/metadata/description",
    response_model=ContentItemResponse,
)
async def update_metadata_description(
    content_item_id: uuid.UUID,
    body: MetadataFieldUpdateRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[MetadataService, Depends(get_metadata_service)],
) -> ContentItemResponse:
    """Update the AI-generated description with creator override."""
    record = await service.update_description(
        session, content_item_id, creator_id, body.value
    )
    return ContentItemResponse.model_validate(record)


@router.patch(
    "/{content_item_id}/metadata/tags",
    response_model=ContentItemResponse,
)
async def update_metadata_tags(
    content_item_id: uuid.UUID,
    body: MetadataTagsUpdateRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[MetadataService, Depends(get_metadata_service)],
) -> ContentItemResponse:
    """Update the AI-generated tags with creator override."""
    record = await service.update_tags(
        session, content_item_id, creator_id, body.tags
    )
    return ContentItemResponse.model_validate(record)


@router.patch(
    "/{content_item_id}/metadata/topic-cluster",
    response_model=ContentItemResponse,
)
async def update_metadata_topic_cluster(
    content_item_id: uuid.UUID,
    body: MetadataFieldUpdateRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[MetadataService, Depends(get_metadata_service)],
) -> ContentItemResponse:
    """Update the AI-generated topic cluster with creator override."""
    record = await service.update_topic_cluster(
        session, content_item_id, creator_id, body.value
    )
    return ContentItemResponse.model_validate(record)


# --- Thumbnail endpoints ---


@router.post(
    "/{content_item_id}/thumbnails/select",
    response_model=ContentItemResponse,
)
async def select_thumbnail(
    content_item_id: uuid.UUID,
    body: ThumbnailSelectionRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ThumbnailService, Depends(get_thumbnail_service)],
) -> ContentItemResponse:
    """Select a thumbnail from available options."""
    record = await service.select_thumbnail(
        session, content_item_id, creator_id, body.selected_thumbnail_url
    )
    return ContentItemResponse.model_validate(record)


# --- Streaming endpoint ---


@router.get(
    "/{content_item_id}/stream",
)
async def stream_assembly_status(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[AssemblyService, Depends(get_assembly_service)],
) -> StreamingResponse:
    """Stream assembly status events via SSE (AG-UI Protocol)."""
    record = await service.get_content_item(session, content_item_id, creator_id)
    return StreamingResponse(
        generate_assembly_events(
            content_item_id=record.content_item_id,
            assembly_status=record.assembly_status,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Version history endpoint ---


@router.get(
    "/{content_item_id}/versions",
    response_model=VersionHistoryResponse,
)
async def get_version_history(
    content_item_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[AssemblyService, Depends(get_assembly_service)],
) -> VersionHistoryResponse:
    """Get version history for a content item."""
    versions = await service.get_version_history(session, content_item_id, creator_id)
    return VersionHistoryResponse(
        content_item_id=content_item_id,
        versions=versions,
    )
