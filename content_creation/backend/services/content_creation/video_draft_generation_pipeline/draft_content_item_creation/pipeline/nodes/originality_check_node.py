"""LangGraph node for originality checking with conditional branching."""

import logging

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.state import (
    DraftContentItemPipelineState,
)

logger = logging.getLogger(__name__)


async def check_originality(
    state: DraftContentItemPipelineState,
) -> DraftContentItemPipelineState:
    """Invoke originality check with conditional branching.

    On success: sets originality_status to 'completed' for pre-publish confirmation.
    On timeout: sets originality_status to 'timeout' for interrupt/resume retry gate.
    On failure: sets error state, Draft is retained.
    """
    content_item_id = state.get("content_item_id")
    creator_id = state.get("creator_id")
    logger.info(
        "Running originality check for content item %s",
        content_item_id,
    )

    try:
        # In production, this node would invoke OriginalityCheckService
        # via RunnableConfig-injected dependencies.
        # Placeholder: simulate successful check
        return {
            **state,
            "originality_status": "completed",
            "originality_report": {
                "duplicate_risk_score": 0,
                "similar_content_items": [],
                "differentiation_recommendations": [],
            },
        }
    except Exception as exc:
        error_msg = str(exc)
        if "timeout" in error_msg.lower():
            logger.warning(
                "Originality check timed out for content item %s",
                content_item_id,
            )
            return {
                **state,
                "originality_status": "timeout",
            }

        logger.error(
            "Originality check failed for content item %s: %s",
            content_item_id,
            exc,
        )
        return {
            **state,
            "error": error_msg,
            "error_node": "originality_check",
        }


def route_originality_result(state: DraftContentItemPipelineState) -> str:
    """Conditional edge router based on originality check result."""
    if state.get("error"):
        return "error"
    originality_status = state.get("originality_status")
    if originality_status == "timeout":
        return "timeout"
    return "completed"
