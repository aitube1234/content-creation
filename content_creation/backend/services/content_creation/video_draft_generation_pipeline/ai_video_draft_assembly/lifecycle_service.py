"""Lifecycle registration service (FR-25 to FR-28)."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
    LifecycleServiceUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.lifecycle_client import (
    LifecycleClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
    LifecycleState,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)

logger = logging.getLogger(__name__)


class LifecycleService:
    """Manages content item lifecycle registration and state transitions (FR-25 to FR-28)."""

    def __init__(
        self,
        repository: ContentItemRepository | None = None,
        lifecycle_client: LifecycleClient | None = None,
    ) -> None:
        self.repository = repository or ContentItemRepository()
        self.lifecycle_client = lifecycle_client or LifecycleClient()

    async def register_draft(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Register a draft content item in lifecycle management (FR-25, FR-26).

        Creates the content item with lifecycle_state=DRAFT and makes it
        visible in the creator's content library.
        """
        record = await self._get_record_or_raise(session, content_item_id, creator_id)

        try:
            await self.lifecycle_client.register_draft(content_item_id, creator_id)
        except LifecycleServiceUnavailableError:
            # FR-27: Block creation if lifecycle service unavailable
            logger.error(
                "Lifecycle service unavailable for content item %s",
                content_item_id,
            )
            raise LifecycleServiceUnavailableError(
                message="Content Lifecycle Management service is unavailable. "
                "Cannot register draft content item.",
            )

        logger.info(
            "Registered draft content item %s in lifecycle management",
            content_item_id,
        )
        return record

    async def transition_to_pre_publish(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Transition a content item to PRE_PUBLISH state."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)

        if record.lifecycle_state != LifecycleState.DRAFT:
            raise ContentItemNotFoundError(
                message=f"Content item must be in DRAFT state to transition to PRE_PUBLISH. Current state: {record.lifecycle_state.value}"
            )

        updated = await self.repository.update(
            session, content_item_id, creator_id,
            {"lifecycle_state": LifecycleState.PRE_PUBLISH},
        )
        if updated is None:
            raise ContentItemNotFoundError(
                message=f"Content item '{content_item_id}' not found."
            )

        logger.info(
            "Transitioned content item %s to PRE_PUBLISH", content_item_id
        )
        return updated

    async def check_service_availability(self) -> bool:
        """Check if the lifecycle management service is available (FR-27)."""
        return await self.lifecycle_client.check_availability()

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
