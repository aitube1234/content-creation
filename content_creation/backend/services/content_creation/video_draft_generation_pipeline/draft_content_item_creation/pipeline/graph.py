"""LangGraph StateGraph definition for the draft content item creation pipeline."""

import logging

from langgraph.graph import END, StateGraph

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.nodes.create_draft_content_item_node import (
    create_draft_content_item,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.nodes.originality_check_node import (
    check_originality,
    route_originality_result,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.nodes.workspace_save_draft_node import (
    workspace_save_draft,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.state import (
    DraftContentItemPipelineState,
)

logger = logging.getLogger(__name__)


def _check_error(state: DraftContentItemPipelineState) -> str:
    """Conditional edge: route to END if an error occurred, otherwise continue."""
    if state.get("error"):
        return "error"
    return "continue"


def build_draft_content_item_graph() -> StateGraph:
    """Build the LangGraph StateGraph for draft content item creation.

    Pipeline flow:
        create_draft_content_item → originality_check → (conditional routing)
            - completed → END
            - timeout → END (with interrupt/resume retry gate)
            - error → END

    A separate workspace_save_draft node handles Co-Creator Workspace saves.
    """
    graph = StateGraph(DraftContentItemPipelineState)

    # Add nodes
    graph.add_node("create_draft_content_item", create_draft_content_item)
    graph.add_node("workspace_save_draft", workspace_save_draft)
    graph.add_node("originality_check", check_originality)

    # Set entry point
    graph.set_entry_point("create_draft_content_item")

    # Add edges
    graph.add_conditional_edges(
        "create_draft_content_item",
        _check_error,
        {"error": END, "continue": "originality_check"},
    )

    graph.add_conditional_edges(
        "workspace_save_draft",
        _check_error,
        {"error": END, "continue": "originality_check"},
    )

    graph.add_conditional_edges(
        "originality_check",
        route_originality_result,
        {"completed": END, "timeout": END, "error": END},
    )

    return graph


def compile_draft_content_item_graph():
    """Compile the draft content item creation graph for execution."""
    graph = build_draft_content_item_graph()
    return graph.compile()
