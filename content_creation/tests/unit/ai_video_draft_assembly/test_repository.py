"""Unit tests for ContentItemRepository."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    ContentItem,
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.repository import (
    ContentItemRepository,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_CREATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def repo():
    return ContentItemRepository()


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_content_item(self, async_session: AsyncSession, repo):
        record = await repo.create(
            async_session,
            {
                "creator_id": CREATOR_ID,
                "input_type": ContentInputType.SCRIPT,
                "input_text": " ".join(["word"] * 100),
                "input_locale": "fr",
            },
        )
        assert record.content_item_id is not None
        assert record.creator_id == CREATOR_ID
        assert record.input_type == ContentInputType.SCRIPT
        assert record.lifecycle_state == LifecycleState.DRAFT
        assert record.assembly_status == AssemblyStatus.PENDING
        assert record.word_count == 100
        assert record.version_history == []


class TestGetById:
    @pytest.mark.asyncio
    async def test_get_existing(self, async_session: AsyncSession, repo, sample_content_item):
        result = await repo.get_by_id(
            async_session, sample_content_item.content_item_id, CREATOR_ID
        )
        assert result is not None
        assert result.content_item_id == sample_content_item.content_item_id

    @pytest.mark.asyncio
    async def test_get_wrong_creator(self, async_session: AsyncSession, repo, sample_content_item):
        result = await repo.get_by_id(
            async_session, sample_content_item.content_item_id, OTHER_CREATOR_ID
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, async_session: AsyncSession, repo):
        result = await repo.get_by_id(async_session, uuid.uuid4(), CREATOR_ID)
        assert result is None


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_fields(self, async_session: AsyncSession, repo, sample_content_item):
        result = await repo.update(
            async_session,
            sample_content_item.content_item_id,
            CREATOR_ID,
            {"ai_title": "Updated Title"},
        )
        assert result is not None
        assert result.ai_title == "Updated Title"


class TestUpdateAssemblyStatus:
    @pytest.mark.asyncio
    async def test_status_transition(self, async_session: AsyncSession, repo, sample_content_item):
        result = await repo.update_assembly_status(
            async_session,
            sample_content_item.content_item_id,
            AssemblyStatus.FAILED,
        )
        assert result is not None
        assert result.assembly_status == AssemblyStatus.FAILED


class TestUpdateScenes:
    @pytest.mark.asyncio
    async def test_update_scenes(self, async_session: AsyncSession, repo, sample_content_item):
        new_scenes = [{"scene_id": "s1", "pacing_value": 2.0}]
        result = await repo.update_scenes(
            async_session, sample_content_item.content_item_id, CREATOR_ID, new_scenes
        )
        assert result is not None
        assert result.scenes == new_scenes


class TestAppendVersionHistory:
    @pytest.mark.asyncio
    async def test_append_entry(self, async_session: AsyncSession, repo, sample_content_item):
        entry = {
            "version_id": str(uuid.uuid4()),
            "change_type": "test_change",
            "changed_fields": {"field": "value"},
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "changed_by": str(CREATOR_ID),
        }
        result = await repo.append_version_history(
            async_session, sample_content_item.content_item_id, CREATOR_ID, entry
        )
        assert result is not None
        assert len(result.version_history) == 1
        assert result.version_history[0]["change_type"] == "test_change"


class TestListByCreator:
    @pytest.mark.asyncio
    async def test_list_returns_items(self, async_session: AsyncSession, repo, sample_content_item):
        records, total = await repo.list_by_creator(async_session, CREATOR_ID)
        assert total >= 1
        assert any(r.content_item_id == sample_content_item.content_item_id for r in records)

    @pytest.mark.asyncio
    async def test_list_filter_by_lifecycle_state(self, async_session: AsyncSession, repo, sample_content_item):
        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, lifecycle_state=LifecycleState.DRAFT
        )
        assert total >= 1
        assert all(r.lifecycle_state == LifecycleState.DRAFT for r in records)

    @pytest.mark.asyncio
    async def test_list_filter_by_assembly_status(self, async_session: AsyncSession, repo, sample_content_item):
        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, assembly_status=AssemblyStatus.COMPLETED
        )
        assert total >= 1
        assert all(r.assembly_status == AssemblyStatus.COMPLETED for r in records)

    @pytest.mark.asyncio
    async def test_list_empty_for_other_creator(self, async_session: AsyncSession, repo, sample_content_item):
        records, total = await repo.list_by_creator(async_session, OTHER_CREATOR_ID)
        assert total == 0
        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_list_pagination(self, async_session: AsyncSession, repo):
        # Create multiple items
        for _ in range(5):
            await repo.create(
                async_session,
                {
                    "creator_id": CREATOR_ID,
                    "input_type": ContentInputType.SCRIPT,
                    "input_text": " ".join(["word"] * 100),
                    "input_locale": "fr",
                },
            )
        await async_session.commit()

        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, offset=0, limit=2
        )
        assert len(records) == 2
        assert total >= 5

    @pytest.mark.asyncio
    async def test_list_sorting(self, async_session: AsyncSession, repo, sample_content_item):
        records_desc, _ = await repo.list_by_creator(
            async_session, CREATOR_ID, sort_by="created_at", sort_order="desc"
        )
        records_asc, _ = await repo.list_by_creator(
            async_session, CREATOR_ID, sort_by="created_at", sort_order="asc"
        )
        if len(records_desc) > 1:
            assert records_desc[0].created_at >= records_desc[-1].created_at
