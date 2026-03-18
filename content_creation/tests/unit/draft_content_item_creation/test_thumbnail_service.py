"""Unit tests for ThumbnailService."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    ThumbnailNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.thumbnail_service import (
    ThumbnailService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_draft_repo():
    return AsyncMock()


@pytest.fixture
def mock_thumbnail_repo():
    return AsyncMock()


@pytest.fixture
def mock_version_history_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_draft_repo, mock_thumbnail_repo, mock_version_history_repo):
    return ThumbnailService(
        draft_repository=mock_draft_repo,
        thumbnail_repository=mock_thumbnail_repo,
        version_history_repository=mock_version_history_repo,
    )


@pytest.mark.asyncio
async def test_store_thumbnails_three_or_more(service, mock_thumbnail_repo):
    """Test presentation of three or more thumbnail options."""
    content_item_id = uuid.uuid4()
    thumbnails = [MagicMock() for _ in range(3)]
    mock_thumbnail_repo.create_many.return_value = thumbnails

    session = AsyncMock()
    result, reduced = await service.store_thumbnails(
        session, content_item_id, ["url1", "url2", "url3"],
    )

    assert len(result) == 3
    assert reduced is False


@pytest.mark.asyncio
async def test_store_thumbnails_reduced_count(service, mock_thumbnail_repo):
    """Test notification on reduced thumbnail count (fewer than three)."""
    content_item_id = uuid.uuid4()
    thumbnails = [MagicMock(), MagicMock()]
    mock_thumbnail_repo.create_many.return_value = thumbnails

    session = AsyncMock()
    result, reduced = await service.store_thumbnails(
        session, content_item_id, ["url1", "url2"],
    )

    assert len(result) == 2
    assert reduced is True


@pytest.mark.asyncio
async def test_select_thumbnail_success(service, mock_draft_repo, mock_thumbnail_repo, mock_version_history_repo):
    """Test creator thumbnail selection."""
    content_item_id = uuid.uuid4()
    thumbnail_id = uuid.uuid4()

    mock_draft = MagicMock()
    mock_draft.selected_thumbnail_id = None
    mock_draft_repo.get_by_id.return_value = mock_draft
    mock_draft_repo.update.return_value = mock_draft

    mock_thumb = MagicMock()
    mock_thumb.content_item_id = content_item_id
    mock_thumbnail_repo.get_by_id.return_value = mock_thumb
    mock_version_history_repo.create.return_value = MagicMock()

    session = AsyncMock()
    result = await service.select_thumbnail(
        session, content_item_id, CREATOR_ID, thumbnail_id,
    )

    assert result is not None
    mock_thumbnail_repo.update_selection.assert_called_once()
    mock_version_history_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_select_thumbnail_not_found(service, mock_draft_repo, mock_thumbnail_repo):
    """Test thumbnail selection fails when thumbnail not found."""
    mock_draft_repo.get_by_id.return_value = MagicMock()
    mock_thumbnail_repo.get_by_id.return_value = None

    session = AsyncMock()
    with pytest.raises(ThumbnailNotFoundError):
        await service.select_thumbnail(session, uuid.uuid4(), CREATOR_ID, uuid.uuid4())


@pytest.mark.asyncio
async def test_auto_select_default(service, mock_draft_repo, mock_thumbnail_repo):
    """Test auto-default selection of first thumbnail when no selection made."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.selected_thumbnail_id = None
    mock_draft_repo.get_by_id.return_value = mock_draft
    mock_draft_repo.update.return_value = mock_draft

    first_thumb = MagicMock()
    first_thumb.thumbnail_id = uuid.uuid4()
    mock_thumbnail_repo.get_by_content_item_id.return_value = [first_thumb, MagicMock()]

    session = AsyncMock()
    result = await service.auto_select_default(session, content_item_id, CREATOR_ID)

    assert result == first_thumb
    mock_thumbnail_repo.update_selection.assert_called_once()


@pytest.mark.asyncio
async def test_auto_select_skips_when_already_selected(service, mock_draft_repo):
    """Test auto-select does nothing when thumbnail already selected."""
    mock_draft = MagicMock()
    mock_draft.selected_thumbnail_id = uuid.uuid4()
    mock_draft_repo.get_by_id.return_value = mock_draft

    session = AsyncMock()
    result = await service.auto_select_default(session, uuid.uuid4(), CREATOR_ID)

    assert result is None


@pytest.mark.asyncio
async def test_get_thumbnails_draft_not_found(service, mock_draft_repo):
    """Test get_thumbnails raises when draft not found."""
    mock_draft_repo.get_by_id.return_value = None

    session = AsyncMock()
    with pytest.raises(DraftContentItemNotFoundError):
        await service.get_thumbnails(session, uuid.uuid4(), CREATOR_ID)
