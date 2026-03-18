"""LangGraph TypedDict state schema for the draft content item creation pipeline."""

import uuid
from typing import TypedDict


class DraftContentItemPipelineState(TypedDict, total=False):
    """State schema for the draft content item creation pipeline StateGraph."""

    content_item_id: uuid.UUID
    creator_id: uuid.UUID
    creation_source: str
    video_draft_url: str | None
    metadata: dict
    thumbnails: list[str]
    originality_report: dict | None
    originality_status: str | None
    error: str | None
    error_node: str | None
    run_id: str
    thread_id: str
