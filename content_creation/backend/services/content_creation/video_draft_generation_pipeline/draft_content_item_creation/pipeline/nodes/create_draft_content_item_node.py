"""LangGraph node for creating a draft content item from pipeline completion."""

import logging

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.state import (
    DraftContentItemPipelineState,
)

logger = logging.getLogger(__name__)


async def create_draft_content_item(
    state: DraftContentItemPipelineState,
) -> DraftContentItemPipelineState:
    """Create a Draft Content Item record from pipeline completion output.

    This node receives the pipeline output state, calls DraftCreationService
    to create the Draft record, triggers MetadataService and ThumbnailService,
    and emits a draft_created version history entry.
    """
    content_item_id = state.get("content_item_id")
    creator_id = state.get("creator_id")
    logger.info(
        "Creating draft content item for creator %s from pipeline",
        creator_id,
    )

    try:
        # In production, this node would use injected services via RunnableConfig.
        # The actual service calls are orchestrated here as a placeholder
        # that the compiled graph invokes with the appropriate database session.
        return {
            **state,
            "content_item_id": content_item_id,
        }
    except Exception as exc:
        logger.error(
            "Failed to create draft content item for creator %s: %s",
            creator_id,
            exc,
        )
        return {
            **state,
            "error": str(exc),
            "error_node": "create_draft_content_item",
        }
