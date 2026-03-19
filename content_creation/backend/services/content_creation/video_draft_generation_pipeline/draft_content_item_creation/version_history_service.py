"""Service for version history management on draft content items."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    ContributionStatus,
    VersionEventType,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    ContributorAccessDeniedError,
    DraftContentItemNotFoundError,
    VersionEntryNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    VersionHistoryEntry,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
    VersionHistoryRepository,
)

logger = logging.getLogger(__name__)


class VersionHistoryService:
    """Creates version history entries and enforces contributor-scoped visibility."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
        version_history_repository: VersionHistoryRepository | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()
        self.version_history_repository = version_history_repository or VersionHistoryRepository()

    async def create_entry(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        event_type: VersionEventType,
        actor_account_id: uuid.UUID,
        actor_role: ActorRole,
        event_payload: dict | None = None,
        contribution_status: ContributionStatus | None = None,
    ) -> VersionHistoryEntry:
        """Create a new version history entry."""
        return await self.version_history_repository.create(
            session,
            {
                "content_item_id": content_item_id,
                "event_type": event_type,
                "actor_account_id": actor_account_id,
                "actor_role": actor_role,
                "event_payload": event_payload,
                "contribution_status": contribution_status,
            },
        )

    async def list_entries(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        requester_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        sort_order: str = "asc",
    ) -> tuple[list[VersionHistoryEntry], int]:
        """List version history entries with contributor-scoped visibility.

        Lead creator sees all entries. Contributors see only their own entries.
        """
        draft = await self.draft_repository.get_by_id(session, content_item_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found.",
            )

        offset = (page - 1) * page_size

        # Lead creator sees all entries; contributor sees only their own
        actor_filter = None
        if draft.lead_creator_account_id != requester_id:
            actor_filter = requester_id

        return await self.version_history_repository.list_by_content_item(
            session,
            content_item_id,
            actor_account_id=actor_filter,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )

    async def accept_contribution(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        version_entry_id: uuid.UUID,
        requester_id: uuid.UUID,
    ) -> VersionHistoryEntry:
        """Lead creator accepts a contributor contribution."""
        await self._verify_lead_creator(session, content_item_id, requester_id)

        entry = await self.version_history_repository.get_by_id(session, version_entry_id)
        if entry is None or entry.content_item_id != content_item_id:
            raise VersionEntryNotFoundError(
                message=f"Version entry '{version_entry_id}' not found for content item '{content_item_id}'.",
            )

        updated = await self.version_history_repository.update_contribution_status(
            session, version_entry_id, ContributionStatus.ACCEPTED,
        )
        logger.info(
            "Contribution %s accepted by lead creator %s",
            version_entry_id,
            requester_id,
        )
        return updated  # type: ignore[return-value]

    async def override_contribution(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        version_entry_id: uuid.UUID,
        requester_id: uuid.UUID,
    ) -> VersionHistoryEntry:
        """Lead creator overrides a contributor contribution."""
        await self._verify_lead_creator(session, content_item_id, requester_id)

        entry = await self.version_history_repository.get_by_id(session, version_entry_id)
        if entry is None or entry.content_item_id != content_item_id:
            raise VersionEntryNotFoundError(
                message=f"Version entry '{version_entry_id}' not found for content item '{content_item_id}'.",
            )

        updated = await self.version_history_repository.update_contribution_status(
            session, version_entry_id, ContributionStatus.OVERRIDDEN,
        )
        logger.info(
            "Contribution %s overridden by lead creator %s",
            version_entry_id,
            requester_id,
        )
        return updated  # type: ignore[return-value]

    async def _verify_lead_creator(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        requester_id: uuid.UUID,
    ) -> None:
        """Verify the requester is the lead creator of the content item."""
        draft = await self.draft_repository.get_by_id(session, content_item_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found.",
            )
        if draft.lead_creator_account_id != requester_id:
            raise ContributorAccessDeniedError(
                message="Only the lead creator can perform this action.",
            )
