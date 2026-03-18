"""Service for AI-generated metadata management."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    MetadataEngineWriteStatus,
    VersionEventType,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    MetadataNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.integrations.originality_engine_client import (
    OriginalityEngineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.models import (
    AIGeneratedMetadata,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.repository import (
    DraftContentItemRepository,
    MetadataRepository,
    VersionHistoryRepository,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """Handles AI metadata generation, engine write, retry, and creator override."""

    def __init__(
        self,
        draft_repository: DraftContentItemRepository | None = None,
        metadata_repository: MetadataRepository | None = None,
        version_history_repository: VersionHistoryRepository | None = None,
    ) -> None:
        self.draft_repository = draft_repository or DraftContentItemRepository()
        self.metadata_repository = metadata_repository or MetadataRepository()
        self.version_history_repository = version_history_repository or VersionHistoryRepository()

    async def generate_and_attach_metadata(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        metadata: dict,
    ) -> AIGeneratedMetadata:
        """Generate and attach AI metadata to a draft content item."""
        record = await self.metadata_repository.create(
            session,
            {
                "content_item_id": content_item_id,
                "ai_title_suggestion": metadata.get("ai_title"),
                "ai_description": metadata.get("ai_description"),
                "ai_topic_tags": metadata.get("ai_tags"),
                "ai_topic_cluster": metadata.get("ai_topic_cluster"),
                "metadata_engine_write_status": MetadataEngineWriteStatus.PENDING,
            },
        )
        await self.draft_repository.update(
            session,
            content_item_id,
            {"metadata_status": MetadataStatus.GENERATED},
        )
        logger.info("Metadata attached to content item %s", content_item_id)
        return record

    async def write_to_metadata_engine(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        metadata_engine_client: object | None = None,
    ) -> bool:
        """Attempt to write metadata to the Content Metadata Engine."""
        metadata = await self.metadata_repository.get_by_content_item_id(
            session, content_item_id,
        )
        if metadata is None:
            raise MetadataNotFoundError(
                message=f"Metadata not found for content item '{content_item_id}'.",
            )

        try:
            if metadata_engine_client and hasattr(metadata_engine_client, "write_metadata"):
                await metadata_engine_client.write_metadata(
                    content_item_id,
                    {
                        "ai_title": metadata.ai_title_suggestion,
                        "ai_description": metadata.ai_description,
                        "ai_tags": metadata.ai_topic_tags,
                        "ai_topic_cluster": metadata.ai_topic_cluster,
                    },
                )
            await self.metadata_repository.update(
                session,
                metadata.metadata_id,
                {"metadata_engine_write_status": MetadataEngineWriteStatus.CONFIRMED},
            )
            logger.info("Metadata engine write confirmed for content item %s", content_item_id)
            return True
        except Exception as exc:
            logger.warning(
                "Metadata engine write failed for content item %s: %s",
                content_item_id,
                exc,
            )
            await self.metadata_repository.update(
                session,
                metadata.metadata_id,
                {"metadata_engine_write_status": MetadataEngineWriteStatus.FAILED},
            )
            await self.draft_repository.update(
                session,
                content_item_id,
                {"metadata_status": MetadataStatus.PENDING},
            )
            return False

    async def override_metadata(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        topic_cluster: str | None = None,
    ) -> AIGeneratedMetadata:
        """Allow lead creator to override metadata fields with version history tracking."""
        # Verify ownership
        draft = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_id}'.",
            )

        metadata = await self.metadata_repository.get_by_content_item_id(
            session, content_item_id,
        )
        if metadata is None:
            raise MetadataNotFoundError(
                message=f"Metadata not found for content item '{content_item_id}'.",
            )

        # Build override data and version history payload
        update_data: dict = {}
        event_payload: dict = {"overrides": {}}

        if title is not None:
            event_payload["overrides"]["title"] = {
                "original": metadata.ai_title_suggestion,
                "override": title,
            }
            update_data["creator_override_title"] = title

        if description is not None:
            event_payload["overrides"]["description"] = {
                "original": metadata.ai_description,
                "override": description,
            }
            update_data["creator_override_description"] = description

        if tags is not None:
            event_payload["overrides"]["tags"] = {
                "original": metadata.ai_topic_tags,
                "override": tags,
            }
            update_data["creator_override_tags"] = tags

        if topic_cluster is not None:
            event_payload["overrides"]["topic_cluster"] = {
                "original": metadata.ai_topic_cluster,
                "override": topic_cluster,
            }

        if update_data:
            await self.metadata_repository.update(session, metadata.metadata_id, update_data)

        # Create version history entry for the override
        await self.version_history_repository.create(
            session,
            {
                "content_item_id": content_item_id,
                "event_type": VersionEventType.METADATA_OVERRIDE,
                "actor_account_id": creator_id,
                "actor_role": ActorRole.LEAD_CREATOR,
                "event_payload": event_payload,
            },
        )

        logger.info("Metadata overridden for content item %s by creator %s", content_item_id, creator_id)

        # Re-fetch updated record
        updated = await self.metadata_repository.get_by_content_item_id(session, content_item_id)
        return updated  # type: ignore[return-value]

    async def get_metadata(
        self,
        session: AsyncSession,
        content_item_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> AIGeneratedMetadata:
        """Retrieve metadata for a draft content item."""
        draft = await self.draft_repository.get_by_id(session, content_item_id, creator_id)
        if draft is None:
            raise DraftContentItemNotFoundError(
                message=f"Draft content item '{content_item_id}' not found for creator '{creator_id}'.",
            )

        metadata = await self.metadata_repository.get_by_content_item_id(
            session, content_item_id,
        )
        if metadata is None:
            raise MetadataNotFoundError(
                message=f"Metadata not found for content item '{content_item_id}'.",
            )
        return metadata
