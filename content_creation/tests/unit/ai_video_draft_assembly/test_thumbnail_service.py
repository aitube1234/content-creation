"""Unit tests for ThumbnailService (FR-21 to FR-24)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.thumbnail_service import (
    ThumbnailService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_item(**overrides) -> MagicMock:
    item = MagicMock(spec=ContentItem)
    item.content_item_id = overrides.get("content_item_id", uuid.uuid4())
    item.creator_id = CREATOR_ID
    item.thumbnail_options = overrides.get("thumbnail_options", [
        "s3://bucket/t1.jpg",
        "s3://bucket/t2.jpg",
        "s3://bucket/t3.jpg",
    ])
    item.selected_thumbnail_url = overrides.get("selected_thumbnail_url", None)
    return item


class TestThumbnailSelection:
    """FR-22: Select a thumbnail from available options."""

    @pytest.fixture
    def service(self):
        return ThumbnailService(repository=AsyncMock())

    @pytest.mark.asyncio
    async def test_select_valid_thumbnail(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_thumbnail_selection = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.select_thumbnail(
            session, item.content_item_id, CREATOR_ID, "s3://bucket/t2.jpg"
        )
        assert result is not None
        service.repository.update_thumbnail_selection.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_invalid_thumbnail(self, service):
        """Selected URL must be in thumbnail_options."""
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.select_thumbnail(
                session, item.content_item_id, CREATOR_ID, "s3://invalid/url.jpg"
            )

    @pytest.mark.asyncio
    async def test_select_thumbnail_not_found(self, service):
        service.repository.get_by_id = AsyncMock(return_value=None)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.select_thumbnail(
                session, uuid.uuid4(), CREATOR_ID, "s3://bucket/t1.jpg"
            )


class TestAutoSelectDefault:
    """FR-24: Auto-select first thumbnail on Pre-Publish without selection."""

    @pytest.fixture
    def service(self):
        return ThumbnailService(repository=AsyncMock())

    @pytest.mark.asyncio
    async def test_auto_select_when_no_selection(self, service):
        item = _make_item(selected_thumbnail_url=None)
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_thumbnail_selection = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.auto_select_default(
            session, item.content_item_id, CREATOR_ID
        )
        assert result is not None
        service.repository.update_thumbnail_selection.assert_called_once_with(
            session, item.content_item_id, CREATOR_ID, "s3://bucket/t1.jpg"
        )

    @pytest.mark.asyncio
    async def test_no_auto_select_when_already_selected(self, service):
        item = _make_item(selected_thumbnail_url="s3://bucket/t2.jpg")
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.auto_select_default(
            session, item.content_item_id, CREATOR_ID
        )
        assert result is not None
        service.repository.update_thumbnail_selection.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_select_no_options(self, service):
        item = _make_item(thumbnail_options=[], selected_thumbnail_url=None)
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.auto_select_default(
            session, item.content_item_id, CREATOR_ID
        )
        assert result is not None
        service.repository.update_thumbnail_selection.assert_not_called()


class TestGetThumbnailOptions:
    """Test getting thumbnail options."""

    @pytest.fixture
    def service(self):
        return ThumbnailService(repository=AsyncMock())

    @pytest.mark.asyncio
    async def test_get_options(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        options = await service.get_thumbnail_options(
            session, item.content_item_id, CREATOR_ID
        )
        assert len(options) == 3
