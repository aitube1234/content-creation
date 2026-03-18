"""LangGraph node for creating a draft from Co-Creator Workspace save event."""

import logging

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.state import (
    DraftContentItemPipelineState,
)

logger = logging.getLogger(__name__)


async def workspace_save_draft(
    state: DraftContentItemPipelineState,
) -> DraftContentItemPipelineState:
    """Create a Draft Content Item from a Co-Creator Workspace save event.

    Sets creation_source to co_creator_workspace and proceeds through
    the same draft creation flow.
    """
    creator_id = state.get("creator_id")
    logger.info(
        "Creating draft content item for creator %s from workspace save",
        creator_id,
    )

    try:
        return {
            **state,
            "creation_source": "co_creator_workspace",
        }
    except Exception as exc:
        logger.error(
            "Failed to create workspace draft for creator %s: %s",
            creator_id,
            exc,
        )
        return {
            **state,
            "error": str(exc),
            "error_node": "workspace_save_draft",
        }
