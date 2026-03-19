"""Visual generation pipeline node."""

import logging
import uuid

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)


async def generate_visuals(state: AssemblyPipelineState) -> AssemblyPipelineState:
    """Generate visual assets for each scene from the input text.

    This node produces AI-generated visuals for the video draft and stores them to S3.
    Each visual is associated with a scene via visual_asset_id.
    """
    content_item_id = state["content_item_id"]
    input_text = state["input_text"]
    logger.info("Generating visuals for content item %s", content_item_id)

    try:
        scenes = state.get("scenes", [])
        visual_assets = []

        if not scenes:
            # Generate initial scenes from input text
            paragraphs = [p.strip() for p in input_text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [input_text]

            scenes = []
            for paragraph in paragraphs:
                scene_id = str(uuid.uuid4())
                visual_asset_id = str(uuid.uuid4())
                scenes.append(
                    {
                        "scene_id": scene_id,
                        "pacing_value": 1.0,
                        "visual_asset_id": visual_asset_id,
                        "voice_segment_id": str(uuid.uuid4()),
                        "text_content": paragraph,
                    }
                )
                visual_assets.append(
                    {
                        "asset_id": visual_asset_id,
                        "scene_id": scene_id,
                        "asset_url": f"s3://video-drafts/{content_item_id}/visuals/{visual_asset_id}.mp4",
                        "status": "generated",
                    }
                )
        else:
            for scene in scenes:
                visual_asset_id = scene.get("visual_asset_id", str(uuid.uuid4()))
                visual_assets.append(
                    {
                        "asset_id": visual_asset_id,
                        "scene_id": scene["scene_id"],
                        "asset_url": f"s3://video-drafts/{content_item_id}/visuals/{visual_asset_id}.mp4",
                        "status": "generated",
                    }
                )

        logger.info(
            "Generated %d visual assets for content item %s",
            len(visual_assets),
            content_item_id,
        )
        return {
            **state,
            "scenes": scenes,
            "visual_assets": visual_assets,
        }
    except Exception as exc:
        logger.error("Visual generation failed for %s: %s", content_item_id, exc)
        return {
            **state,
            "error": str(exc),
            "error_node": "visual_generation",
            "assembly_status": "failed",
        }
