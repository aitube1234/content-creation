"""Thumbnail generation and selection service (FR-21 to FR-24)."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
    ThumbnailGenerationError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)

logger = logging.getLogger(__name__)

MINIMUM_THUMBNAILS = 3


class ThumbnailService:
    """Manages thumbnail generation, selection, and default assignment (FR-21 to FR-24)."""

    def __init__(
        self,
        repository: ContentItemRepository | None = None,
    ) -> None:
        self.repository = repository or ContentItemRepository()

    async def select_thumbnail(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        selected_url: str,
    ) -> ContentItem:
        """Select a thumbnail from available options (FR-22).

        Validates that the selected URL is in thumbnail_options.
        """
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        options = record.thumbnail_options or []

        if selected_url not in options:
            raise ContentItemNotFoundError(
                message=f"Selected thumbnail URL is not in available options.",
                details=[f"Available options: {options}"],
            )

        await self.repository.update_thumbnail_selection(
            session, content_item_id, creator_id, selected_url
        )

        logger.info(
            "Thumbnail selected for content item %s: %s",
            content_item_id, selected_url,
        )
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def auto_select_default(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Auto-select first thumbnail on Pre-Publish without selection (FR-24).

        If no thumbnail has been selected and the item is transitioning to Pre-Publish,
        automatically attach the first thumbnail option.
        """
        record = await self._get_record_or_raise(session, content_item_id, creator_id)

        if record.selected_thumbnail_url:
            return record

        options = record.thumbnail_options or []
        if options:
            selected_url = options[0]
            await self.repository.update_thumbnail_selection(
                session, content_item_id, creator_id, selected_url
            )
            logger.info(
                "Auto-selected default thumbnail for content item %s: %s",
                content_item_id, selected_url,
            )
            return await self._get_record_or_raise(session, content_item_id, creator_id)

        return record

    async def get_thumbnail_options(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> list[str]:
        """Get available thumbnail options for a content item."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        return list(record.thumbnail_options or [])

    async def _get_record_or_raise(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Fetch a record or raise ContentItemNotFoundError."""
        record = await self.repository.get_by_id(session, content_item_id, creator_id)
        if record is None:
            raise ContentItemNotFoundError(
                message=f"Content item '{content_item_id}' not found for creator '{creator_id}'."
            )
        return record
