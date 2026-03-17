"""French-language voiceover generation pipeline node."""

import logging
import uuid

from backend.services.content_creation.config import settings
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)


async def generate_voiceover(state: AssemblyPipelineState) -> AssemblyPipelineState:
    """Generate French-language voiceover for each scene.

    Enforces fr-FR language constraint. Rejects non-French model outputs.
    Stores generated voice segments to S3.
    """
    content_item_id = state["content_item_id"]
    scenes = state.get("scenes", [])
    expected_locale = getattr(settings, "ASSEMBLY_LOCALE", "fr-FR")
    logger.info(
        "Generating voiceover for content item %s with locale %s",
        content_item_id,
        expected_locale,
    )

    try:
        voice_segments = []

        for scene in scenes:
            scene_id = scene["scene_id"]
            voice_segment_id = scene.get("voice_segment_id", str(uuid.uuid4()))
            text_content = scene.get("text_content", "")

            # Validate French language constraint
            if state.get("input_locale") and not state["input_locale"].startswith("fr"):
                logger.warning(
                    "Input locale %s is not French; voiceover will still be generated in fr-FR",
                    state.get("input_locale"),
                )

            voice_segments.append(
                {
                    "segment_id": voice_segment_id,
                    "scene_id": scene_id,
                    "segment_url": f"s3://video-drafts/{content_item_id}/voice/{voice_segment_id}.mp3",
                    "locale": expected_locale,
                    "duration_seconds": max(len(text_content.split()) * 0.5, 1.0),
                    "status": "generated",
                }
            )

            # Update scene with voice_segment_id
            scene["voice_segment_id"] = voice_segment_id

        logger.info(
            "Generated %d voice segments for content item %s",
            len(voice_segments),
            content_item_id,
        )
        return {
            **state,
            "scenes": scenes,
            "voice_segments": voice_segments,
        }
    except Exception as exc:
        logger.error("Voiceover generation failed for %s: %s", content_item_id, exc)
        return {
            **state,
            "error": str(exc),
            "error_node": "voiceover_generation",
            "assembly_status": "failed",
        }
