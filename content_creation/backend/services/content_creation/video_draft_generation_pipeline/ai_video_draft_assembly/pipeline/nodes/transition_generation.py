"""Transition generation pipeline node."""

import logging
import uuid

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)


async def generate_transitions(state: AssemblyPipelineState) -> AssemblyPipelineState:
    """Generate transitions between consecutive scenes.

    Produces transition effects (crossfade, cut, dissolve) between
    adjacent scenes in the sequence.
    """
    content_item_id = state["content_item_id"]
    scenes = state.get("scenes", [])
    logger.info(
        "Generating transitions for %d scenes in content item %s",
        len(scenes),
        content_item_id,
    )

    try:
        transitions = []
        transition_types = ["crossfade", "cut", "dissolve", "fade_to_black"]

        for i in range(len(scenes) - 1):
            from_scene = scenes[i]
            to_scene = scenes[i + 1]
            transition_type = transition_types[i % len(transition_types)]

            transitions.append(
                {
                    "transition_id": str(uuid.uuid4()),
                    "from_scene_id": from_scene["scene_id"],
                    "to_scene_id": to_scene["scene_id"],
                    "transition_type": transition_type,
                    "duration_seconds": 0.5,
                }
            )

        logger.info(
            "Generated %d transitions for content item %s",
            len(transitions),
            content_item_id,
        )
        return {**state, "transitions": transitions}
    except Exception as exc:
        logger.error("Transition generation failed for %s: %s", content_item_id, exc)
        return {
            **state,
            "error": str(exc),
            "error_node": "transition_generation",
            "assembly_status": "failed",
        }
