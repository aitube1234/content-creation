"""Repository layer for draft content item database access."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ContributionStatus,
    CreationSource,
    MetadataEngineWriteStatus,
    ReportStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    AIGeneratedMetadata,
    AIGeneratedThumbnail,
    DraftContentItem,
    OriginalityReport,
    VersionHistoryEntry,
)

logger = logging.getLogger(__name__)


class DraftContentItemRepository:
    """Async CRUD operations for the draft_content_items table."""

    async def create(
        self,
        session: AsyncSession,
        data: dict[str, Any],
    ) -> DraftContentItem:
        """Insert a new draft content item record."""
        record = DraftContentItem(
            content_item_id=uuid.uuid4(),
            lead_creator_account_id=data["lead_creator_account_id"],
            creation_source=data["creation_source"],
            video_draft_url=data.get("video_draft_url"),
            lifecycle_state=data.get("lifecycle_state", LifecycleState.DRAFT),
            metadata_status=data.get("metadata_status", MetadataStatus.PENDING),
            pipeline_job_reference=data.get("pipeline_job_reference"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        logger.debug(
            "Created draft content item %s for creator %s",
            record.content_item_id,
            record.lead_creator_account_id,
        )
        return record

    async def get_by_id(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID | None = None,
    ) -> DraftContentItem | None:
        """Fetch a single draft content item, optionally scoped to creator."""
        stmt = select(DraftContentItem).where(
            DraftContentItem.content_item_id == content_item_id,
        )
        if creator_id is not None:
            stmt = stmt.where(DraftContentItem.lead_creator_account_id == creator_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        data: dict[str, Any],
    ) -> DraftContentItem | None:
        """Update mutable fields on a draft content item."""
        update_data: dict[str, Any] = {
            **data,
            "updated_at": datetime.now(timezone.utc),
        }
        stmt = (
            update(DraftContentItem)
            .where(DraftContentItem.content_item_id == content_item_id)
            .values(**update_data)
            .returning(DraftContentItem)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
            logger.debug("Updated draft content item %s", content_item_id)
        return record

    async def delete(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
    ) -> bool:
        """Delete a draft content item and cascade to related records."""
        stmt = delete(DraftContentItem).where(
            DraftContentItem.content_item_id == content_item_id,
        )
        result = await session.execute(stmt)
        await session.flush()
        deleted = result.rowcount > 0
        if deleted:
            logger.debug("Deleted draft content item %s", content_item_id)
        return deleted

    async def list_by_creator(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        lifecycle_state: LifecycleState | None = None,
        metadata_status: MetadataStatus | None = None,
        creation_source: CreationSource | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DraftContentItem], int]:
        """Paginated, filterable, sortable draft content item list."""
        base_filter = DraftContentItem.lead_creator_account_id == creator_id

        count_stmt = select(func.count()).select_from(DraftContentItem).where(base_filter)
        query_stmt = select(DraftContentItem).where(base_filter)

        if lifecycle_state is not None:
            count_stmt = count_stmt.where(DraftContentItem.lifecycle_state == lifecycle_state)
            query_stmt = query_stmt.where(DraftContentItem.lifecycle_state == lifecycle_state)
        if metadata_status is not None:
            count_stmt = count_stmt.where(DraftContentItem.metadata_status == metadata_status)
            query_stmt = query_stmt.where(DraftContentItem.metadata_status == metadata_status)
        if creation_source is not None:
            count_stmt = count_stmt.where(DraftContentItem.creation_source == creation_source)
            query_stmt = query_stmt.where(DraftContentItem.creation_source == creation_source)

        sort_column = getattr(DraftContentItem, sort_by, DraftContentItem.created_at)
        if sort_order == "asc":
            query_stmt = query_stmt.order_by(sort_column.asc())
        else:
            query_stmt = query_stmt.order_by(sort_column.desc())

        query_stmt = query_stmt.offset(offset).limit(limit)

        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        records_result = await session.execute(query_stmt)
        records = list(records_result.scalars().all())

        return records, total


class MetadataRepository:
    """Async CRUD operations for the ai_generated_metadata table."""

    async def create(
        self,
        session: AsyncSession,
        data: dict[str, Any],
    ) -> AIGeneratedMetadata:
        """Insert a new metadata record."""
        record = AIGeneratedMetadata(
            metadata_id=uuid.uuid4(),
            content_item_id=data["content_item_id"],
            ai_title_suggestion=data.get("ai_title_suggestion"),
            ai_description=data.get("ai_description"),
            ai_topic_tags=data.get("ai_topic_tags"),
            ai_topic_cluster=data.get("ai_topic_cluster"),
            metadata_engine_write_status=data.get(
                "metadata_engine_write_status", MetadataEngineWriteStatus.PENDING
            ),
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        logger.debug("Created metadata %s for content item %s", record.metadata_id, record.content_item_id)
        return record

    async def get_by_content_item_id(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
    ) -> AIGeneratedMetadata | None:
        """Fetch metadata by content item ID."""
        stmt = select(AIGeneratedMetadata).where(
            AIGeneratedMetadata.content_item_id == content_item_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        session: AsyncSession,
        metadata_id: uuid.UUID,
        data: dict[str, Any],
    ) -> AIGeneratedMetadata | None:
        """Update metadata fields."""
        stmt = (
            update(AIGeneratedMetadata)
            .where(AIGeneratedMetadata.metadata_id == metadata_id)
            .values(**data)
            .returning(AIGeneratedMetadata)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
        return record


class ThumbnailRepository:
    """Async CRUD operations for the ai_generated_thumbnails table."""

    async def create_many(
        self,
        session: AsyncSession,
        thumbnails: list[dict[str, Any]],
    ) -> list[AIGeneratedThumbnail]:
        """Insert multiple thumbnail records."""
        records = []
        for idx, thumb_data in enumerate(thumbnails):
            record = AIGeneratedThumbnail(
                thumbnail_id=uuid.uuid4(),
                content_item_id=thumb_data["content_item_id"],
                thumbnail_url=thumb_data["thumbnail_url"],
                display_order=thumb_data.get("display_order", idx),
                is_selected=thumb_data.get("is_selected", False),
                created_at=datetime.now(timezone.utc),
            )
            session.add(record)
            records.append(record)
        await session.flush()
        return records

    async def get_by_content_item_id(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
    ) -> list[AIGeneratedThumbnail]:
        """Fetch all thumbnails for a content item, ordered by display_order."""
        stmt = (
            select(AIGeneratedThumbnail)
            .where(AIGeneratedThumbnail.content_item_id == content_item_id)
            .order_by(AIGeneratedThumbnail.display_order.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(
        self,
        session: AsyncSession,
        thumbnail_id: uuid.UUID,
    ) -> AIGeneratedThumbnail | None:
        """Fetch a single thumbnail by ID."""
        stmt = select(AIGeneratedThumbnail).where(
            AIGeneratedThumbnail.thumbnail_id == thumbnail_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_selection(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        selected_thumbnail_id: uuid.UUID,
    ) -> None:
        """Set the selected thumbnail, deselecting all others for the content item."""
        # Deselect all
        deselect_stmt = (
            update(AIGeneratedThumbnail)
            .where(AIGeneratedThumbnail.content_item_id == content_item_id)
            .values(is_selected=False)
        )
        await session.execute(deselect_stmt)

        # Select the chosen one
        select_stmt = (
            update(AIGeneratedThumbnail)
            .where(AIGeneratedThumbnail.thumbnail_id == selected_thumbnail_id)
            .values(is_selected=True)
        )
        await session.execute(select_stmt)
        await session.flush()


class VersionHistoryRepository:
    """Async operations for the version_history_entries table."""

    async def create(
        self,
        session: AsyncSession,
        data: dict[str, Any],
    ) -> VersionHistoryEntry:
        """Insert a new version history entry."""
        record = VersionHistoryEntry(
            version_entry_id=uuid.uuid4(),
            content_item_id=data["content_item_id"],
            event_type=data["event_type"],
            actor_account_id=data["actor_account_id"],
            actor_role=data["actor_role"],
            event_payload=data.get("event_payload"),
            contribution_status=data.get("contribution_status"),
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        return record

    async def list_by_content_item(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        actor_account_id: uuid.UUID | None = None,
        sort_order: str = "asc",
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[VersionHistoryEntry], int]:
        """Paginated list of version history entries, optionally scoped to an actor."""
        base_filter = VersionHistoryEntry.content_item_id == content_item_id

        count_stmt = select(func.count()).select_from(VersionHistoryEntry).where(base_filter)
        query_stmt = select(VersionHistoryEntry).where(base_filter)

        if actor_account_id is not None:
            count_stmt = count_stmt.where(
                VersionHistoryEntry.actor_account_id == actor_account_id,
            )
            query_stmt = query_stmt.where(
                VersionHistoryEntry.actor_account_id == actor_account_id,
            )

        if sort_order == "desc":
            query_stmt = query_stmt.order_by(VersionHistoryEntry.created_at.desc())
        else:
            query_stmt = query_stmt.order_by(VersionHistoryEntry.created_at.asc())

        query_stmt = query_stmt.offset(offset).limit(limit)

        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        records_result = await session.execute(query_stmt)
        records = list(records_result.scalars().all())

        return records, total

    async def get_by_id(
        self,
        session: AsyncSession,
        version_entry_id: uuid.UUID,
    ) -> VersionHistoryEntry | None:
        """Fetch a single version history entry by ID."""
        stmt = select(VersionHistoryEntry).where(
            VersionHistoryEntry.version_entry_id == version_entry_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_contribution_status(
        self,
        session: AsyncSession,
        version_entry_id: uuid.UUID,
        status: ContributionStatus,
    ) -> VersionHistoryEntry | None:
        """Update the contribution status of a version history entry."""
        stmt = (
            update(VersionHistoryEntry)
            .where(VersionHistoryEntry.version_entry_id == version_entry_id)
            .values(contribution_status=status)
            .returning(VersionHistoryEntry)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
        return record


class OriginalityReportRepository:
    """Async operations for the originality_reports table."""

    async def create(
        self,
        session: AsyncSession,
        data: dict[str, Any],
    ) -> OriginalityReport:
        """Insert a new originality report."""
        record = OriginalityReport(
            originality_report_id=uuid.uuid4(),
            content_item_id=data["content_item_id"],
            creator_account_id=data["creator_account_id"],
            duplicate_risk_score=data.get("duplicate_risk_score", 0),
            similar_content_items=data.get("similar_content_items"),
            differentiation_recommendations=data.get("differentiation_recommendations"),
            report_status=data["report_status"],
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        return record

    async def get_by_content_item_id(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
    ) -> OriginalityReport | None:
        """Fetch the latest originality report for a content item."""
        stmt = (
            select(OriginalityReport)
            .where(OriginalityReport.content_item_id == content_item_id)
            .order_by(OriginalityReport.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_content_and_creator(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_account_id: uuid.UUID,
    ) -> OriginalityReport | None:
        """Fetch originality report by content item and creator."""
        stmt = (
            select(OriginalityReport)
            .where(
                OriginalityReport.content_item_id == content_item_id,
                OriginalityReport.creator_account_id == creator_account_id,
            )
            .order_by(OriginalityReport.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
