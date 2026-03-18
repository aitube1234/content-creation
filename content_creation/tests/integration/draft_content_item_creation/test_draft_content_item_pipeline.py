"""Integration tests for Draft Content Item LangGraph pipeline nodes."""

import uuid

import pytest

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


@pytest.mark.asyncio
async def test_create_draft_content_item_node():
    """Test create_draft_content_item node executes without error."""
    state: DraftContentItemPipelineState = {
        "content_item_id": uuid.uuid4(),
        "creator_id": uuid.uuid4(),
        "creation_source": "script_to_video",
        "video_draft_url": "s3://video-drafts/test/video.mp4",
        "metadata": {"ai_title": "Test Title"},
        "thumbnails": ["url1", "url2", "url3"],
        "run_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
    }

    result = await create_draft_content_item(state)

    assert result.get("error") is None
    assert result["content_item_id"] == state["content_item_id"]


@pytest.mark.asyncio
async def test_workspace_save_draft_node():
    """Test workspace_save_draft node sets creation_source correctly."""
    state: DraftContentItemPipelineState = {
        "content_item_id": uuid.uuid4(),
        "creator_id": uuid.uuid4(),
        "creation_source": "script_to_video",
        "video_draft_url": "s3://workspace/video.mp4",
        "metadata": {},
        "thumbnails": [],
        "run_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
    }

    result = await workspace_save_draft(state)

    assert result.get("error") is None
    assert result["creation_source"] == "co_creator_workspace"


@pytest.mark.asyncio
async def test_originality_check_node_success():
    """Test originality_check node returns completed status on success."""
    state: DraftContentItemPipelineState = {
        "content_item_id": uuid.uuid4(),
        "creator_id": uuid.uuid4(),
        "creation_source": "script_to_video",
        "video_draft_url": "s3://video.mp4",
        "metadata": {},
        "thumbnails": [],
        "run_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
    }

    result = await check_originality(state)

    assert result.get("error") is None
    assert result["originality_status"] == "completed"
    assert result["originality_report"] is not None


def test_route_originality_result_completed():
    """Test routing function returns 'completed' on success."""
    state = {"originality_status": "completed"}
    assert route_originality_result(state) == "completed"


def test_route_originality_result_timeout():
    """Test routing function returns 'timeout' on timeout."""
    state = {"originality_status": "timeout"}
    assert route_originality_result(state) == "timeout"


def test_route_originality_result_error():
    """Test routing function returns 'error' when error present."""
    state = {"error": "Something went wrong"}
    assert route_originality_result(state) == "error"


@pytest.mark.asyncio
async def test_pipeline_graph_compiles():
    """Test the draft content item pipeline graph compiles without error."""
    from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.graph import (
        compile_draft_content_item_graph,
    )

    compiled = compile_draft_content_item_graph()
    assert compiled is not None


@pytest.mark.asyncio
async def test_pipeline_graph_invocation():
    """Test full pipeline graph invocation with test state."""
    from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.pipeline.graph import (
        compile_draft_content_item_graph,
    )

    compiled = compile_draft_content_item_graph()

    initial_state: DraftContentItemPipelineState = {
        "content_item_id": uuid.uuid4(),
        "creator_id": uuid.uuid4(),
        "creation_source": "script_to_video",
        "video_draft_url": "s3://video.mp4",
        "metadata": {},
        "thumbnails": [],
        "run_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
    }

    result = await compiled.ainvoke(initial_state)

    assert result.get("error") is None
    assert result.get("originality_status") == "completed"
