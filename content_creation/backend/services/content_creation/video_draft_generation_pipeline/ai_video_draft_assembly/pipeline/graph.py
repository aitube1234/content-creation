"""LangGraph StateGraph definition for the AI assembly pipeline."""

import logging

from langgraph.graph import END, StateGraph

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.metadata_generation import (
    generate_metadata,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.scene_sequencing import (
    sequence_scenes,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.thumbnail_generation import (
    generate_thumbnails,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.transition_generation import (
    generate_transitions,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.visual_generation import (
    generate_visuals,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.voiceover_generation import (
    generate_voiceover,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)


def _check_error(state: AssemblyPipelineState) -> str:
    """Conditional edge: route to END if an error occurred, otherwise continue."""
    if state.get("error"):
        return "error"
    return "continue"


def build_assembly_graph() -> StateGraph:
    """Build and compile the LangGraph StateGraph for the AI assembly pipeline.

    Pipeline flow:
        visual_generation → voiceover_generation → scene_sequencing →
        transition_generation → metadata_generation → thumbnail_generation → finalize

    Each node has a conditional edge that routes to END on error.
    """
    graph = StateGraph(AssemblyPipelineState)

    # Add nodes
    graph.add_node("visual_generation", generate_visuals)
    graph.add_node("voiceover_generation", generate_voiceover)
    graph.add_node("scene_sequencing", sequence_scenes)
    graph.add_node("transition_generation", generate_transitions)
    graph.add_node("metadata_generation", generate_metadata)
    graph.add_node("thumbnail_generation", generate_thumbnails)

    # Set entry point
    graph.set_entry_point("visual_generation")

    # Add conditional edges for error handling after each node
    graph.add_conditional_edges(
        "visual_generation",
        _check_error,
        {"error": END, "continue": "voiceover_generation"},
    )
    graph.add_conditional_edges(
        "voiceover_generation",
        _check_error,
        {"error": END, "continue": "scene_sequencing"},
    )
    graph.add_conditional_edges(
        "scene_sequencing",
        _check_error,
        {"error": END, "continue": "transition_generation"},
    )
    graph.add_conditional_edges(
        "transition_generation",
        _check_error,
        {"error": END, "continue": "metadata_generation"},
    )
    graph.add_conditional_edges(
        "metadata_generation",
        _check_error,
        {"error": END, "continue": "thumbnail_generation"},
    )
    graph.add_edge("thumbnail_generation", END)

    return graph


def compile_assembly_graph():
    """Compile the assembly graph for execution."""
    graph = build_assembly_graph()
    return graph.compile()
