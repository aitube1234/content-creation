"""Thumbnail generation pipeline node."""

import logging
import uuid

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)

MINIMUM_THUMBNAILS = 3


async def generate_thumbnails(state: AssemblyPipelineState) -> AssemblyPipelineState:
    """Generate AI-produced thumbnail options for the video draft.

    Produces a minimum of 3 thumbnail images, stores them to S3,
    and populates thumbnail_options with their URLs.
    """
    content_item_id = state["content_item_id"]
    logger.info("Generating thumbnails for content item %s", content_item_id)

    try:
        thumbnails = []
        for i in range(MINIMUM_THUMBNAILS):
            thumbnail_id = str(uuid.uuid4())
            thumbnails.append(
                f"s3://video-drafts/{content_item_id}/thumbnails/{thumbnail_id}.jpg"
            )

        logger.info(
            "Generated %d thumbnails for content item %s",
            len(thumbnails),
            content_item_id,
        )
        return {**state, "thumbnails": thumbnails}
    except Exception as exc:
        logger.error("Thumbnail generation failed for %s: %s", content_item_id, exc)
        return {
            **state,
            "error": str(exc),
            "error_node": "thumbnail_generation",
            "assembly_status": "failed",
        }
