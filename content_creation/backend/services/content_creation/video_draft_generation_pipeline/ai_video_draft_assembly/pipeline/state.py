"""LangGraph TypedDict state schema for the assembly pipeline."""

import uuid
from typing import TypedDict


class AssemblyPipelineState(TypedDict, total=False):
    """State schema for the AI video draft assembly pipeline StateGraph."""

    content_item_id: uuid.UUID
    creator_id: uuid.UUID
    input_text: str
    input_type: str
    input_locale: str | None
    scenes: list[dict]
    visual_assets: list[dict]
    voice_segments: list[dict]
    transitions: list[dict]
    metadata: dict
    thumbnails: list[str]
    assembly_status: str
    video_draft_url: str | None
    error: str | None
    error_node: str | None
    run_id: str
    thread_id: str
