"""Repository layer for content item database access."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    ContentItem,
    LifecycleState,
    MetadataStatus,
)

logger = logging.getLogger(__name__)


class ContentItemRepository:
    """Provides all async database access methods for ContentItem."""

    async def create(
        self,
        session: AsyncSession,
        data: dict[str, Any],
    ) -> ContentItem:
        """Insert a new content item record."""
        record = ContentItem(
            content_item_id=uuid.uuid4(),
            creator_id=data["creator_id"],
            input_type=data["input_type"],
            input_text=data["input_text"],
            input_locale=data.get("input_locale"),
            lifecycle_state=data.get("lifecycle_state", LifecycleState.DRAFT),
            assembly_status=data.get("assembly_status", AssemblyStatus.PENDING),
            word_count=len(data["input_text"].split()),
            version_history=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        logger.debug(
            "Created content item %s for creator %s",
            record.content_item_id,
            record.creator_id,
        )
        return record

    async def get_by_id(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem | None:
        """Fetch a single content item scoped to the creator."""
        stmt = select(ContentItem).where(
            ContentItem.content_item_id == content_item_id,
            ContentItem.creator_id == creator_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        data: dict[str, Any],
    ) -> ContentItem | None:
        """Update mutable fields on a content item."""
        update_data: dict[str, Any] = {
            **data,
            "updated_at": datetime.now(timezone.utc),
        }
        stmt = (
            update(ContentItem)
            .where(
                ContentItem.content_item_id == content_item_id,
                ContentItem.creator_id == creator_id,
            )
            .values(**update_data)
            .returning(ContentItem)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
            logger.debug("Updated content item %s", content_item_id)
        return record

    async def update_assembly_status(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        new_status: AssemblyStatus,
        extra_fields: dict[str, Any] | None = None,
    ) -> ContentItem | None:
        """Atomic assembly status update with optional extra field updates."""
        update_data: dict[str, Any] = {
            "assembly_status": new_status,
            "updated_at": datetime.now(timezone.utc),
        }
        if extra_fields:
            update_data.update(extra_fields)

        stmt = (
            update(ContentItem)
            .where(ContentItem.content_item_id == content_item_id)
            .values(**update_data)
            .returning(ContentItem)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
            logger.debug(
                "Updated assembly status for %s to %s",
                content_item_id,
                new_status.value,
            )
        return record

    async def update_scenes(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        scenes: list[dict],
    ) -> ContentItem | None:
        """Update the scenes JSONB column."""
        return await self.update(
            session, content_item_id, creator_id, {"scenes": scenes}
        )

    async def append_version_history(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        entry: dict,
    ) -> ContentItem | None:
        """Append a version entry to the version_history array."""
        record = await self.get_by_id(session, content_item_id, creator_id)
        if record is None:
            return None
        history = list(record.version_history or [])
        history.append(entry)
        return await self.update(
            session, content_item_id, creator_id, {"version_history": history}
        )

    async def update_metadata(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        metadata_fields: dict[str, Any],
    ) -> ContentItem | None:
        """Update metadata fields on a content item."""
        return await self.update(
            session, content_item_id, creator_id, metadata_fields
        )

    async def update_thumbnail_selection(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        selected_url: str,
    ) -> ContentItem | None:
        """Set the selected thumbnail URL."""
        return await self.update(
            session, content_item_id, creator_id, {"selected_thumbnail_url": selected_url}
        )

    async def list_by_creator(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        lifecycle_state: LifecycleState | None = None,
        assembly_status: AssemblyStatus | None = None,
        metadata_status: MetadataStatus | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ContentItem], int]:
        """Paginated, filterable, sortable content item list."""
        base_filter = ContentItem.creator_id == creator_id

        count_stmt = select(func.count()).select_from(ContentItem).where(base_filter)
        query_stmt = select(ContentItem).where(base_filter)

        if lifecycle_state is not None:
            count_stmt = count_stmt.where(ContentItem.lifecycle_state == lifecycle_state)
            query_stmt = query_stmt.where(ContentItem.lifecycle_state == lifecycle_state)
        if assembly_status is not None:
            count_stmt = count_stmt.where(ContentItem.assembly_status == assembly_status)
            query_stmt = query_stmt.where(ContentItem.assembly_status == assembly_status)
        if metadata_status is not None:
            count_stmt = count_stmt.where(ContentItem.metadata_status == metadata_status)
            query_stmt = query_stmt.where(ContentItem.metadata_status == metadata_status)

        sort_column = getattr(ContentItem, sort_by, ContentItem.created_at)
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
