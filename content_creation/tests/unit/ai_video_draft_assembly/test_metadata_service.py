"""Unit tests for MetadataService (FR-17 to FR-20)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.metadata_service import (
    MetadataService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_item(**overrides) -> MagicMock:
    item = MagicMock(spec=ContentItem)
    item.content_item_id = overrides.get("content_item_id", uuid.uuid4())
    item.creator_id = CREATOR_ID
    item.input_text = " ".join(["word"] * 150)
    item.ai_title = overrides.get("ai_title", "Original Title")
    item.ai_description = overrides.get("ai_description", "Original Desc")
    item.ai_tags = overrides.get("ai_tags", ["tag1", "tag2"])
    item.ai_topic_cluster = overrides.get("ai_topic_cluster", "general")
    item.metadata_status = overrides.get("metadata_status", MetadataStatus.GENERATED)
    item.version_history = overrides.get("version_history", [])
    return item


class TestUpdateTitle:
    """FR-19: Creator override of AI title."""

    @pytest.fixture
    def service(self):
        return MetadataService(
            repository=AsyncMock(),
            metadata_engine_client=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_update_title_success(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_metadata = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.update_title(
            session, item.content_item_id, CREATOR_ID, "New Title"
        )
        assert result is not None
        service.repository.update_metadata.assert_called_once()
        # Verify metadata_status is set to MANUALLY_ENTERED
        call_args = service.repository.update_metadata.call_args[0][3]
        assert call_args["metadata_status"] == MetadataStatus.MANUALLY_ENTERED

    @pytest.mark.asyncio
    async def test_update_title_not_found(self, service):
        service.repository.get_by_id = AsyncMock(return_value=None)
        session = AsyncMock()
        with pytest.raises(ContentItemNotFoundError):
            await service.update_title(session, uuid.uuid4(), CREATOR_ID, "New Title")


class TestUpdateDescription:
    """FR-19: Creator override of AI description."""

    @pytest.fixture
    def service(self):
        return MetadataService(repository=AsyncMock(), metadata_engine_client=AsyncMock())

    @pytest.mark.asyncio
    async def test_update_description_success(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_metadata = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.update_description(
            session, item.content_item_id, CREATOR_ID, "New Description"
        )
        assert result is not None


class TestUpdateTags:
    """FR-19: Creator override of AI tags."""

    @pytest.fixture
    def service(self):
        return MetadataService(repository=AsyncMock(), metadata_engine_client=AsyncMock())

    @pytest.mark.asyncio
    async def test_update_tags_success(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_metadata = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.update_tags(
            session, item.content_item_id, CREATOR_ID, ["new_tag1", "new_tag2"]
        )
        assert result is not None


class TestUpdateTopicCluster:
    """FR-19: Creator override of AI topic cluster."""

    @pytest.fixture
    def service(self):
        return MetadataService(repository=AsyncMock(), metadata_engine_client=AsyncMock())

    @pytest.mark.asyncio
    async def test_update_topic_cluster_success(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_metadata = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.update_topic_cluster(
            session, item.content_item_id, CREATOR_ID, "technologie"
        )
        assert result is not None


class TestVersionHistoryPreservation:
    """FR-19: Original AI-generated values preserved in version_history."""

    @pytest.fixture
    def service(self):
        return MetadataService(repository=AsyncMock(), metadata_engine_client=AsyncMock())

    @pytest.mark.asyncio
    async def test_title_override_preserves_original(self, service):
        item = _make_item(ai_title="AI Generated Title")
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_metadata = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        await service.update_title(
            session, item.content_item_id, CREATOR_ID, "Creator Override"
        )

        call_args = service.repository.append_version_history.call_args[0][3]
        assert call_args["change_type"] == "metadata_title_override"
        assert call_args["changed_fields"]["old_title"] == "AI Generated Title"
        assert call_args["changed_fields"]["new_title"] == "Creator Override"


class TestMetadataWriteFailure:
    """FR-18, FR-20: Metadata engine write failure handling."""

    @pytest.fixture
    def service(self):
        svc = MetadataService(
            repository=AsyncMock(),
            metadata_engine_client=AsyncMock(),
        )
        return svc

    @pytest.mark.asyncio
    async def test_write_failure_marks_pending(self, service):
        """FR-18: On metadata engine write failure, mark as PENDING."""
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_metadata = AsyncMock(return_value=item)
        service.metadata_engine_client.write_metadata = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        session = AsyncMock()

        await service.trigger_metadata_generation(
            session, item.content_item_id, CREATOR_ID
        )

        # Verify update_metadata was called with PENDING status
        calls = service.repository.update_metadata.call_args_list
        # The second call should set metadata_status to PENDING
        assert any(
            call[0][3].get("metadata_status") == MetadataStatus.PENDING
            for call in calls
        )
