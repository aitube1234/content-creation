"""Unit tests for MetadataService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    MetadataEngineWriteStatus,
    VersionEventType,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    MetadataNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.metadata_service import (
    MetadataService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_draft_repo():
    return AsyncMock()


@pytest.fixture
def mock_metadata_repo():
    return AsyncMock()


@pytest.fixture
def mock_version_history_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_draft_repo, mock_metadata_repo, mock_version_history_repo):
    return MetadataService(
        draft_repository=mock_draft_repo,
        metadata_repository=mock_metadata_repo,
        version_history_repository=mock_version_history_repo,
    )


@pytest.mark.asyncio
async def test_generate_and_attach_metadata(service, mock_metadata_repo, mock_draft_repo):
    """Test successful AI metadata generation and attachment."""
    content_item_id = uuid.uuid4()
    mock_metadata_repo.create.return_value = MagicMock()
    mock_draft_repo.update.return_value = MagicMock()

    session = AsyncMock()
    result = await service.generate_and_attach_metadata(
        session,
        content_item_id,
        {"ai_title": "Title", "ai_description": "Desc", "ai_tags": ["tag"], "ai_topic_cluster": "general"},
    )

    assert result is not None
    mock_metadata_repo.create.assert_called_once()
    mock_draft_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_write_to_metadata_engine_success(service, mock_metadata_repo):
    """Test successful metadata write to engine."""
    metadata_record = MagicMock()
    metadata_record.metadata_id = uuid.uuid4()
    metadata_record.ai_title_suggestion = "Title"
    metadata_record.ai_description = "Desc"
    metadata_record.ai_topic_tags = ["tag"]
    metadata_record.ai_topic_cluster = "general"
    mock_metadata_repo.get_by_content_item_id.return_value = metadata_record
    mock_metadata_repo.update.return_value = metadata_record

    engine_client = AsyncMock()
    engine_client.write_metadata = AsyncMock(return_value=True)

    session = AsyncMock()
    result = await service.write_to_metadata_engine(
        session, uuid.uuid4(), metadata_engine_client=engine_client,
    )

    assert result is True
    mock_metadata_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_write_to_metadata_engine_failure(service, mock_metadata_repo, mock_draft_repo):
    """Test metadata engine write failure triggers pending status."""
    metadata_record = MagicMock()
    metadata_record.metadata_id = uuid.uuid4()
    metadata_record.ai_title_suggestion = "Title"
    metadata_record.ai_description = "Desc"
    metadata_record.ai_topic_tags = ["tag"]
    metadata_record.ai_topic_cluster = "general"
    mock_metadata_repo.get_by_content_item_id.return_value = metadata_record
    mock_metadata_repo.update.return_value = metadata_record
    mock_draft_repo.update.return_value = MagicMock()

    engine_client = AsyncMock()
    engine_client.write_metadata = AsyncMock(side_effect=Exception("Connection refused"))

    session = AsyncMock()
    result = await service.write_to_metadata_engine(
        session, uuid.uuid4(), metadata_engine_client=engine_client,
    )

    assert result is False


@pytest.mark.asyncio
async def test_override_metadata_preserves_original(service, mock_draft_repo, mock_metadata_repo, mock_version_history_repo):
    """Test creator override preserves original AI-generated values in version history."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft_repo.get_by_id.return_value = mock_draft

    metadata_record = MagicMock()
    metadata_record.metadata_id = uuid.uuid4()
    metadata_record.ai_title_suggestion = "Original Title"
    metadata_record.ai_description = "Original Description"
    metadata_record.ai_topic_tags = ["orig_tag"]
    metadata_record.ai_topic_cluster = "general"
    mock_metadata_repo.get_by_content_item_id.return_value = metadata_record
    mock_metadata_repo.update.return_value = metadata_record
    mock_version_history_repo.create.return_value = MagicMock()

    session = AsyncMock()
    await service.override_metadata(
        session, content_item_id, CREATOR_ID,
        title="New Title",
        description="New Description",
    )

    # Verify version history entry was created with original values
    version_call = mock_version_history_repo.create.call_args
    payload = version_call[0][1]["event_payload"]
    assert payload["overrides"]["title"]["original"] == "Original Title"
    assert payload["overrides"]["title"]["override"] == "New Title"
    assert payload["overrides"]["description"]["original"] == "Original Description"


@pytest.mark.asyncio
async def test_override_metadata_not_found(service, mock_draft_repo, mock_metadata_repo):
    """Test override raises when metadata not found."""
    mock_draft_repo.get_by_id.return_value = MagicMock()
    mock_metadata_repo.get_by_content_item_id.return_value = None

    session = AsyncMock()
    with pytest.raises(MetadataNotFoundError):
        await service.override_metadata(session, uuid.uuid4(), CREATOR_ID, title="New")


@pytest.mark.asyncio
async def test_get_metadata_draft_not_found(service, mock_draft_repo):
    """Test get_metadata raises when draft not found."""
    mock_draft_repo.get_by_id.return_value = None

    session = AsyncMock()
    with pytest.raises(DraftContentItemNotFoundError):
        await service.get_metadata(session, uuid.uuid4(), CREATOR_ID)
