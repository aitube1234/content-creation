"""Service for thumbnail management on draft content items."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    VersionEventType,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    ThumbnailNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    AIGeneratedThumbnail,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
    ThumbnailRepository,
    VersionHistoryRepository,
)

logger = logging.getLogger(__name__)

THUMBNAIL_MIN_COUNT = getattr(settings, "THUMBNAIL_MIN_COUNT", 3)


class ThumbnailService:
    """Manages thumbnail presentation, selection, and auto-default logic."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
        thumbnail_repository: ThumbnailRepository | None = None,
        version_history_repository: VersionHistoryRepository | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()
        self.thumbnail_repository = thumbnail_repository or ThumbnailRepository()
        self.version_history_repository = version_history_repository or VersionHistoryRepository()

    async def store_thumbnails(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        thumbnail_urls: list[str],
    ) -> tuple[list[AIGeneratedThumbnail], bool]:
        """Store AI-generated thumbnails. Returns (thumbnails, reduced_notice)."""
        thumb_data = [
            {
                "content_item_id": content_item_id,
                "thumbnail_url": url,
                "display_order": idx,
            }
            for idx, url in enumerate(thumbnail_urls)
        ]
        records = await self.thumbnail_repository.create_many(session, thumb_data)

        reduced_notice = len(records) < THUMBNAIL_MIN_COUNT
        if reduced_notice:
            logger.warning(
                "Reduced thumbnail count (%d < %d) for content item %s",
                len(records),
                THUMBNAIL_MIN_COUNT,
                content_item_id,
            )

        return records, reduced_notice

    async def select_thumbnail(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        thumbnail_id: uuid.UUID,
    ) -> AIGeneratedThumbnail:
        """Set the selected thumbnail by ID."""
        draft = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_id}'.",
            )

        thumbnail = await self.thumbnail_repository.get_by_id(session, thumbnail_id)
        if thumbnail is None or thumbnail.content_item_id != content_item_id:
            raise ThumbnailNotFoundError(
                message=f"Thumbnail '{thumbnail_id}' not found for content item '{content_item_id}'.",
            )

        # Update selection
        await self.thumbnail_repository.update_selection(session, content_item_id, thumbnail_id)

        # Update draft's selected_thumbnail_id
        await self.draft_repository.update(
            session,
            content_item_id,
            {"selected_thumbnail_id": thumbnail_id},
        )

        # Create version history entry
        await self.version_history_repository.create(
            session,
            {
                "content_item_id": content_item_id,
                "event_type": VersionEventType.THUMBNAIL_CHANGE,
                "actor_account_id": creator_id,
                "actor_role": ActorRole.LEAD_CREATOR,
                "event_payload": {
                    "previous_thumbnail_id": str(draft.selected_thumbnail_id) if draft.selected_thumbnail_id else None,
                    "new_thumbnail_id": str(thumbnail_id),
                },
            },
        )

        logger.info(
            "Thumbnail %s selected for content item %s by creator %s",
            thumbnail_id,
            content_item_id,
            creator_id,
        )
        return thumbnail

    async def auto_select_default(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> AIGeneratedThumbnail | None:
        """Auto-select the first thumbnail if no selection has been made."""
        draft = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if draft is None or draft.selected_thumbnail_id is not None:
            return None

        thumbnails = await self.thumbnail_repository.get_by_content_item_id(
            session, content_item_id,
        )
        if not thumbnails:
            return None

        first = thumbnails[0]
        await self.thumbnail_repository.update_selection(
            session, content_item_id, first.thumbnail_id,
        )
        await self.draft_repository.update(
            session,
            content_item_id,
            {"selected_thumbnail_id": first.thumbnail_id},
        )

        logger.info(
            "Auto-selected default thumbnail %s for content item %s",
            first.thumbnail_id,
            content_item_id,
        )
        return first

    async def get_thumbnails(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> list[AIGeneratedThumbnail]:
        """Retrieve all thumbnails for a draft content item."""
        draft = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_id}'.",
            )
        return await self.thumbnail_repository.get_by_content_item_id(
            session, content_item_id,
        )
