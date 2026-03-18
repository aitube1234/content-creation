"""Unit tests for SceneEditService (FR-11 to FR-16)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
    MicrophonePermissionError,
    SceneNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    ContentItem,
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.scene_edit_service import (
    SceneEditService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_content_item_with_scenes() -> MagicMock:
    """Create a mock ContentItem with two scenes."""
    item = MagicMock(spec=ContentItem)
    item.content_item_id = uuid.uuid4()
    item.creator_id = CREATOR_ID
    item.scenes = [
        {
            "scene_id": "scene-001",
            "pacing_value": 1.0,
            "visual_asset_id": "visual-001",
            "voice_segment_id": "voice-001",
        },
        {
            "scene_id": "scene-002",
            "pacing_value": 1.5,
            "visual_asset_id": "visual-002",
            "voice_segment_id": "voice-002",
        },
    ]
    item.version_history = []
    return item


class TestPacingAdjustment:
    """FR-12: Pacing adjustment tests."""

    @pytest.fixture
    def service(self):
        repo = AsyncMock()
        return SceneEditService(repository=repo)

    @pytest.mark.asyncio
    async def test_update_pacing_success(self, service):
        item = _make_content_item_with_scenes()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_scenes = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)

        session = AsyncMock()
        result = await service.update_pacing(
            session, item.content_item_id, CREATOR_ID, "scene-001", 2.0
        )
        assert result is not None
        service.repository.update_scenes.assert_called_once()
        service.repository.append_version_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_pacing_scene_not_found(self, service):
        item = _make_content_item_with_scenes()
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        with pytest.raises(SceneNotFoundError):
            await service.update_pacing(
                session, item.content_item_id, CREATOR_ID, "nonexistent", 2.0
            )


class TestVisualSwap:
    """FR-13: Visual swap tests."""

    @pytest.fixture
    def service(self):
        return SceneEditService(repository=AsyncMock())

    @pytest.mark.asyncio
    async def test_swap_visual_success(self, service):
        item = _make_content_item_with_scenes()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_scenes = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        new_visual_id = str(uuid.uuid4())
        result = await service.swap_visual(
            session, item.content_item_id, CREATOR_ID, "scene-001", new_visual_id
        )
        assert result is not None
        service.repository.update_scenes.assert_called_once()

    @pytest.mark.asyncio
    async def test_swap_visual_scene_not_found(self, service):
        item = _make_content_item_with_scenes()
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        with pytest.raises(SceneNotFoundError):
            await service.swap_visual(
                session, item.content_item_id, CREATOR_ID, "nonexistent", "new-visual"
            )


class TestVoiceReRecording:
    """FR-14, FR-15: Voice re-recording tests."""

    @pytest.fixture
    def service(self):
        return SceneEditService(repository=AsyncMock())

    @pytest.mark.asyncio
    async def test_re_record_voice_success(self, service):
        item = _make_content_item_with_scenes()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_scenes = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.re_record_voice(
            session, item.content_item_id, CREATOR_ID, "scene-001",
            "s3://voice/new.mp3", has_microphone_access=True
        )
        assert result is not None
        service.repository.update_scenes.assert_called_once()

    @pytest.mark.asyncio
    async def test_re_record_voice_no_microphone(self, service):
        """FR-15: Microphone permission error."""
        session = AsyncMock()
        with pytest.raises(MicrophonePermissionError):
            await service.re_record_voice(
                session, uuid.uuid4(), CREATOR_ID, "scene-001",
                "s3://voice/new.mp3", has_microphone_access=False
            )

    @pytest.mark.asyncio
    async def test_re_record_voice_content_not_found(self, service):
        service.repository.get_by_id = AsyncMock(return_value=None)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.re_record_voice(
                session, uuid.uuid4(), CREATOR_ID, "scene-001",
                "s3://voice/new.mp3"
            )


class TestVersionHistory:
    """FR-16: Version history append on scene edits."""

    @pytest.fixture
    def service(self):
        return SceneEditService(repository=AsyncMock())

    @pytest.mark.asyncio
    async def test_pacing_appends_version_entry(self, service):
        item = _make_content_item_with_scenes()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update_scenes = AsyncMock(return_value=item)
        service.repository.append_version_history = AsyncMock(return_value=item)
        session = AsyncMock()

        await service.update_pacing(
            session, item.content_item_id, CREATOR_ID, "scene-001", 2.0
        )

        service.repository.append_version_history.assert_called_once()
        call_args = service.repository.append_version_history.call_args
        entry = call_args[0][3]  # 4th positional arg is the entry dict
        assert entry["change_type"] == "pacing_adjustment"
        assert "changed_at" in entry
        assert "version_id" in entry
