"""Metadata generation and management service (FR-17 to FR-20)."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
    MetadataGenerationError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.integrations.metadata_engine_client import (
    MetadataEngineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """Manages AI metadata generation and creator overrides (FR-17 to FR-20)."""

    def __init__(
        self,
        repository: ContentItemRepository | None = None,
        metadata_engine_client: MetadataEngineClient | None = None,
    ) -> None:
        self.repository = repository or ContentItemRepository()
        self.metadata_engine_client = metadata_engine_client or MetadataEngineClient()

    async def update_title(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        title: str,
    ) -> ContentItem:
        """Update the AI title with creator override (FR-19)."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        old_title = record.ai_title

        await self.repository.update_metadata(
            session, content_item_id, creator_id,
            {"ai_title": title, "metadata_status": MetadataStatus.MANUALLY_ENTERED},
        )
        await self._append_version_entry(
            session, content_item_id, creator_id,
            "metadata_title_override",
            {"old_title": old_title, "new_title": title},
        )

        logger.info("Updated title for content item %s", content_item_id)
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def update_description(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        description: str,
    ) -> ContentItem:
        """Update the AI description with creator override (FR-19)."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        old_description = record.ai_description

        await self.repository.update_metadata(
            session, content_item_id, creator_id,
            {"ai_description": description, "metadata_status": MetadataStatus.MANUALLY_ENTERED},
        )
        await self._append_version_entry(
            session, content_item_id, creator_id,
            "metadata_description_override",
            {"old_description": old_description, "new_description": description},
        )

        logger.info("Updated description for content item %s", content_item_id)
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def update_tags(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        tags: list[str],
    ) -> ContentItem:
        """Update the AI tags with creator override (FR-19)."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        old_tags = record.ai_tags

        await self.repository.update_metadata(
            session, content_item_id, creator_id,
            {"ai_tags": tags, "metadata_status": MetadataStatus.MANUALLY_ENTERED},
        )
        await self._append_version_entry(
            session, content_item_id, creator_id,
            "metadata_tags_override",
            {"old_tags": old_tags, "new_tags": tags},
        )

        logger.info("Updated tags for content item %s", content_item_id)
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def update_topic_cluster(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        topic_cluster: str,
    ) -> ContentItem:
        """Update the AI topic cluster with creator override (FR-19)."""
        record = await self._get_record_or_raise(session, content_item_id, creator_id)
        old_cluster = record.ai_topic_cluster

        await self.repository.update_metadata(
            session, content_item_id, creator_id,
            {"ai_topic_cluster": topic_cluster, "metadata_status": MetadataStatus.MANUALLY_ENTERED},
        )
        await self._append_version_entry(
            session, content_item_id, creator_id,
            "metadata_topic_cluster_override",
            {"old_topic_cluster": old_cluster, "new_topic_cluster": topic_cluster},
        )

        logger.info("Updated topic cluster for content item %s", content_item_id)
        return await self._get_record_or_raise(session, content_item_id, creator_id)

    async def trigger_metadata_generation(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ContentItem:
        """Trigger AI metadata generation for a content item (FR-17).

        Called immediately upon video draft creation. Generates title, description,
        tags, and topic cluster, then writes to the metadata engine (FR-18).
        """
        record = await self._get_record_or_raise(session, content_item_id, creator_id)

        try:
            from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.metadata_generation import (
                _classify_topic,
                _extract_tags,
            )

            words = record.input_text.split()
            title = " ".join(words[:8]) if len(words) >= 8 else " ".join(words)
            description = " ".join(words[:30]) if len(words) >= 30 else " ".join(words)
            tags = _extract_tags(record.input_text)
            topic_cluster = _classify_topic(record.input_text)

            metadata_fields = {
                "ai_title": title,
                "ai_description": description,
                "ai_tags": tags,
                "ai_topic_cluster": topic_cluster,
                "metadata_status": MetadataStatus.GENERATED,
            }

            await self.repository.update_metadata(
                session, content_item_id, creator_id, metadata_fields
            )

            # FR-18: Write to metadata engine
            try:
                await self.metadata_engine_client.write_metadata(
                    content_item_id, metadata_fields
                )
            except Exception:
                logger.warning(
                    "Metadata engine write failed for %s; marking as PENDING",
                    content_item_id,
                )
                await self.repository.update_metadata(
                    session, content_item_id, creator_id,
                    {"metadata_status": MetadataStatus.PENDING},
                )

            return await self._get_record_or_raise(session, content_item_id, creator_id)

        except Exception as exc:
            # FR-20: On generation failure, set PENDING and enable manual entry
            logger.error(
                "Metadata generation failed for content item %s: %s",
                content_item_id, exc,
            )
            await self.repository.update_metadata(
                session, content_item_id, creator_id,
                {"metadata_status": MetadataStatus.PENDING},
            )
            raise MetadataGenerationError(
                message=f"AI metadata generation failed: {exc}",
                details=[str(exc)],
            )

    async def _append_version_entry(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        change_type: str,
        changed_fields: dict,
    ) -> None:
        """Append a version entry preserving original AI-generated values."""
        entry = {
            "version_id": str(uuid.uuid4()),
            "change_type": change_type,
            "changed_fields": changed_fields,
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "changed_by": str(creator_id),
        }
        await self.repository.append_version_history(
            session, content_item_id, creator_id, entry
        )

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
