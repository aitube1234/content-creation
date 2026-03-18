"""Scene sequencing pipeline node."""

import logging

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)


async def sequence_scenes(state: AssemblyPipelineState) -> AssemblyPipelineState:
    """Order scenes and set pacing for the video draft.

    Assigns sequence indices and calculates scene timing based on
    voice segment durations and pacing values.
    """
    content_item_id = state["content_item_id"]
    scenes = state.get("scenes", [])
    voice_segments = state.get("voice_segments", [])
    logger.info("Sequencing %d scenes for content item %s", len(scenes), content_item_id)

    try:
        voice_duration_map = {
            seg["scene_id"]: seg.get("duration_seconds", 3.0)
            for seg in voice_segments
        }

        for idx, scene in enumerate(scenes):
            scene_id = scene["scene_id"]
            pacing = scene.get("pacing_value", 1.0)
            base_duration = voice_duration_map.get(scene_id, 3.0)
            scene["sequence_index"] = idx
            scene["duration_seconds"] = base_duration * pacing
            scene["start_time"] = sum(
                s.get("duration_seconds", 3.0) for s in scenes[:idx]
            )

        logger.info("Scene sequencing completed for content item %s", content_item_id)
        return {**state, "scenes": scenes}
    except Exception as exc:
        logger.error("Scene sequencing failed for %s: %s", content_item_id, exc)
        return {
            **state,
            "error": str(exc),
            "error_node": "scene_sequencing",
            "assembly_status": "failed",
        }
