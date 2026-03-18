"""Service for querying draft content items."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    CreationSource,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    DraftContentItem,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
)

logger = logging.getLogger(__name__)


class DraftQueryService:
    """Handles retrieval and listing of draft content items."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()

    async def get_draft_content_item(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> DraftContentItem:
        """Fetch a single draft content item by ID scoped to the creator."""
        record = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if record is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_id}'.",
            )
        return record

    async def list_draft_content_items(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        lifecycle_state: LifecycleState | None = None,
        metadata_status: MetadataStatus | None = None,
        creation_source: CreationSource | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DraftContentItem], int]:
        """Return paginated, filtered, sorted draft content items."""
        offset = (page - 1) * page_size
        return await self.draft_repository.list_by_creator(
            session,
            creator_id,
            lifecycle_state=lifecycle_state,
            metadata_status=metadata_status,
            creation_source=creation_source,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )
