"""Unit tests for DraftCreationService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.draft_creation_service import (
    DraftCreationService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    CreationSource,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    DraftNotDeletableError,
)


CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_draft_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_metadata_repo():
    return AsyncMock()


@pytest.fixture
def mock_thumbnail_repo():
    return AsyncMock()


@pytest.fixture
def mock_version_history_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_draft_repo, mock_metadata_repo, mock_thumbnail_repo, mock_version_history_repo):
    return DraftCreationService(
        draft_repository=mock_draft_repo,
        metadata_repository=mock_metadata_repo,
        thumbnail_repository=mock_thumbnail_repo,
        version_history_repository=mock_version_history_repo,
    )


@pytest.mark.asyncio
async def test_create_draft_from_pipeline(service, mock_draft_repo, mock_metadata_repo, mock_thumbnail_repo, mock_version_history_repo):
    """Test successful Draft creation from pipeline completion."""
    content_item_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.content_item_id = content_item_id
    mock_record.lead_creator_account_id = CREATOR_ID
    mock_record.lifecycle_state = LifecycleState.DRAFT

    mock_draft_repo.create.return_value = mock_record
    mock_draft_repo.get_by_id.return_value = mock_record
    mock_draft_repo.update.return_value = mock_record
    mock_metadata_repo.create.return_value = MagicMock()
    mock_thumbnail_repo.create_many.return_value = []
    mock_version_history_repo.create.return_value = MagicMock()

    session = AsyncMock(spec=AsyncSession)
    result = await service.create_draft_from_pipeline(
        session,
        lead_creator_account_id=CREATOR_ID,
        video_draft_url="s3://bucket/video.mp4",
        metadata={"ai_title": "Test", "ai_description": "Desc", "ai_tags": ["tag"], "ai_topic_cluster": "general"},
        thumbnails=["url1", "url2", "url3"],
    )

    assert result is not None
    mock_draft_repo.create.assert_called_once()
    mock_metadata_repo.create.assert_called_once()
    mock_thumbnail_repo.create_many.assert_called_once()
    mock_version_history_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_draft_from_workspace(service, mock_draft_repo, mock_version_history_repo):
    """Test successful Draft creation from workspace save."""
    content_item_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.content_item_id = content_item_id
    mock_record.lead_creator_account_id = CREATOR_ID

    mock_draft_repo.create.return_value = mock_record
    mock_draft_repo.get_by_id.return_value = mock_record
    mock_version_history_repo.create.return_value = MagicMock()

    session = AsyncMock(spec=AsyncSession)
    result = await service.create_draft_from_workspace(
        session,
        lead_creator_account_id=CREATOR_ID,
        video_draft_url="s3://bucket/workspace.mp4",
    )

    assert result is not None
    create_call = mock_draft_repo.create.call_args
    assert create_call[0][1]["creation_source"] == CreationSource.CO_CREATOR_WORKSPACE


@pytest.mark.asyncio
async def test_delete_draft_success(service, mock_draft_repo):
    """Test successful deletion of a Draft content item."""
    content_item_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.lifecycle_state = LifecycleState.DRAFT
    mock_draft_repo.get_by_id.return_value = mock_record
    mock_draft_repo.delete.return_value = True

    session = AsyncMock(spec=AsyncSession)
    await service.delete_draft(session, content_item_id, CREATOR_ID)

    mock_draft_repo.delete.assert_called_once_with(session, content_item_id)


@pytest.mark.asyncio
async def test_delete_draft_not_deletable(service, mock_draft_repo):
    """Test deletion fails when lifecycle_state is not Draft."""
    content_item_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.lifecycle_state = LifecycleState.PRE_PUBLISH
    mock_draft_repo.get_by_id.return_value = mock_record

    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(DraftNotDeletableError):
        await service.delete_draft(session, content_item_id, CREATOR_ID)


@pytest.mark.asyncio
async def test_delete_draft_not_found(service, mock_draft_repo):
    """Test deletion fails when content item not found."""
    mock_draft_repo.get_by_id.return_value = None

    session = AsyncMock(spec=AsyncSession)
    with pytest.raises(DraftContentItemNotFoundError):
        await service.delete_draft(session, uuid.uuid4(), CREATOR_ID)


@pytest.mark.asyncio
async def test_create_draft_without_metadata(service, mock_draft_repo, mock_metadata_repo, mock_version_history_repo):
    """Test Draft creation without metadata triggers metadata_pending status."""
    content_item_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.content_item_id = content_item_id
    mock_record.lead_creator_account_id = CREATOR_ID

    mock_draft_repo.create.return_value = mock_record
    mock_draft_repo.get_by_id.return_value = mock_record
    mock_version_history_repo.create.return_value = MagicMock()

    session = AsyncMock(spec=AsyncSession)
    await service.create_draft_from_pipeline(
        session,
        lead_creator_account_id=CREATOR_ID,
        video_draft_url="s3://bucket/video.mp4",
    )

    mock_metadata_repo.create.assert_not_called()
