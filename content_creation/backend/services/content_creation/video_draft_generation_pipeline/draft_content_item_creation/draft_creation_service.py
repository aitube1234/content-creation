"""Service for draft content item creation and deletion."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    CreationSource,
    VersionEventType,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    DraftNotDeletableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    DraftContentItem,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
    MetadataRepository,
    ThumbnailRepository,
    VersionHistoryRepository,
)

logger = logging.getLogger(__name__)


class DraftCreationService:
    """Orchestrates Draft Content Item creation, deletion, and related record generation."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
        metadata_repository: MetadataRepository | None = None,
        thumbnail_repository: ThumbnailRepository | None = None,
        version_history_repository: VersionHistoryRepository | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()
        self.metadata_repository = metadata_repository or MetadataRepository()
        self.thumbnail_repository = thumbnail_repository or ThumbnailRepository()
        self.version_history_repository = version_history_repository or VersionHistoryRepository()

    async def create_draft_from_pipeline(
        self,
        session: AsyncSession,
        lead_creator_account_id: uuid.UUID,
        video_draft_url: str,
        pipeline_job_reference: str | None = None,
        metadata: dict | None = None,
        thumbnails: list[str] | None = None,
    ) -> DraftContentItem:
        """Create a Draft Content Item from AI Video Draft Generation pipeline completion."""
        return await self._create_draft(
            session,
            lead_creator_account_id=lead_creator_account_id,
            creation_source=CreationSource.SCRIPT_TO_VIDEO,
            video_draft_url=video_draft_url,
            pipeline_job_reference=pipeline_job_reference,
            metadata=metadata,
            thumbnails=thumbnails,
        )

    async def create_draft_from_workspace(
        self,
        session: AsyncSession,
        lead_creator_account_id: uuid.UUID,
        video_draft_url: str,
        pipeline_job_reference: str | None = None,
        metadata: dict | None = None,
        thumbnails: list[str] | None = None,
    ) -> DraftContentItem:
        """Create a Draft Content Item from Co-Creator Workspace save event."""
        return await self._create_draft(
            session,
            lead_creator_account_id=lead_creator_account_id,
            creation_source=CreationSource.CO_CREATOR_WORKSPACE,
            video_draft_url=video_draft_url,
            pipeline_job_reference=pipeline_job_reference,
            metadata=metadata,
            thumbnails=thumbnails,
        )

    async def create_draft(
        self,
        session: AsyncSession,
        lead_creator_account_id: uuid.UUID,
        creation_source: CreationSource,
        video_draft_url: str,
        pipeline_job_reference: str | None = None,
        metadata: dict | None = None,
        thumbnails: list[str] | None = None,
    ) -> DraftContentItem:
        """Create a Draft Content Item from any source."""
        return await self._create_draft(
            session,
            lead_creator_account_id=lead_creator_account_id,
            creation_source=creation_source,
            video_draft_url=video_draft_url,
            pipeline_job_reference=pipeline_job_reference,
            metadata=metadata,
            thumbnails=thumbnails,
        )

    async def _create_draft(
        self,
        session: AsyncSession,
        lead_creator_account_id: uuid.UUID,
        creation_source: CreationSource,
        video_draft_url: str,
        pipeline_job_reference: str | None = None,
        metadata: dict | None = None,
        thumbnails: list[str] | None = None,
    ) -> DraftContentItem:
        """Internal method to create a draft content item with all associated records."""
        # Create the draft record
        record = await self.draft_repository.create(
            session,
            {
                "lead_creator_account_id": lead_creator_account_id,
                "creation_source": creation_source,
                "video_draft_url": video_draft_url,
                "pipeline_job_reference": pipeline_job_reference,
                "lifecycle_state": LifecycleState.DRAFT,
                "metadata_status": MetadataStatus.PENDING,
            },
        )

        content_item_id = record.content_item_id

        # Generate and attach metadata if provided
        if metadata:
            metadata_status = MetadataStatus.GENERATED
            await self.metadata_repository.create(
                session,
                {
                    "content_item_id": content_item_id,
                    "ai_title_suggestion": metadata.get("ai_title"),
                    "ai_description": metadata.get("ai_description"),
                    "ai_topic_tags": metadata.get("ai_tags"),
                    "ai_topic_cluster": metadata.get("ai_topic_cluster"),
                },
            )
            await self.draft_repository.update(
                session,
                content_item_id,
                {"metadata_status": metadata_status},
            )
        else:
            metadata_status = MetadataStatus.PENDING

        # Store thumbnails if provided
        if thumbnails:
            thumb_data = [
                {
                    "content_item_id": content_item_id,
                    "thumbnail_url": url,
                    "display_order": idx,
                }
                for idx, url in enumerate(thumbnails)
            ]
            await self.thumbnail_repository.create_many(session, thumb_data)

        # Create draft_created version history entry
        await self.version_history_repository.create(
            session,
            {
                "content_item_id": content_item_id,
                "event_type": VersionEventType.DRAFT_CREATED,
                "actor_account_id": lead_creator_account_id,
                "actor_role": ActorRole.LEAD_CREATOR,
                "event_payload": {
                    "creation_source": creation_source.value,
                    "video_draft_url": video_draft_url,
                },
            },
        )

        logger.info(
            "Draft content item %s created by creator %s via %s",
            content_item_id,
            lead_creator_account_id,
            creation_source.value,
        )

        # Re-fetch to get relationships loaded
        return await self._get_or_raise(session, content_item_id, lead_creator_account_id)

    async def delete_draft(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> None:
        """Delete a draft content item. Only allowed when lifecycle_state is Draft."""
        record = await self._get_or_raise(session, content_item_id, creator_id)

        if record.lifecycle_state != LifecycleState.DRAFT:
            raise DraftNotDeletableError(
                message=f"Cannot delete draft content item '{content_item_id}' in '{record.lifecycle_state.value}' state. Only Draft items can be deleted.",
            )

        await self.draft_repository.delete(session, content_item_id)
        logger.info("Deleted draft content item %s", content_item_id)

    async def _get_or_raise(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> DraftContentItem:
        """Fetch a record or raise DraftContentItemNotFoundError."""
        record = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if record is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_id}'.",
            )
        return record
