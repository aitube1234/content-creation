"""Integration tests for ContentItemRepository against in-memory SQLite."""

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


class TestCreateIntegration:
    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, async_session: AsyncSession, repo):
        """Full cycle: create → get_by_id → verify all fields."""
        record = await repo.create(
            async_session,
            {
                "creator_id": CREATOR_ID,
                "input_type": ContentInputType.SCRIPT,
                "input_text": " ".join(["bonjour"] * 100),
                "input_locale": "fr",
            },
        )
        await async_session.commit()

        fetched = await repo.get_by_id(
            async_session, record.content_item_id, CREATOR_ID
        )
        assert fetched is not None
        assert fetched.content_item_id == record.content_item_id
        assert fetched.creator_id == CREATOR_ID
        assert fetched.input_type == ContentInputType.SCRIPT
        assert fetched.lifecycle_state == LifecycleState.DRAFT
        assert fetched.assembly_status == AssemblyStatus.PENDING
        assert fetched.word_count == 100
        assert fetched.input_locale == "fr"


class TestUpdateIntegration:
    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, async_session: AsyncSession, repo):
        record = await repo.create(
            async_session,
            {
                "creator_id": CREATOR_ID,
                "input_type": ContentInputType.TOPIC_PROMPT,
                "input_text": " ".join(["mot"] * 30),
                "input_locale": "fr",
            },
        )
        await async_session.commit()

        updated = await repo.update(
            async_session,
            record.content_item_id,
            CREATOR_ID,
            {
                "ai_title": "Mon Titre",
                "ai_description": "Ma Description",
                "ai_tags": ["tag1", "tag2"],
                "metadata_status": MetadataStatus.GENERATED,
            },
        )
        await async_session.commit()

        assert updated is not None
        assert updated.ai_title == "Mon Titre"
        assert updated.ai_description == "Ma Description"
        assert updated.ai_tags == ["tag1", "tag2"]
        assert updated.metadata_status == MetadataStatus.GENERATED


class TestAssemblyStatusIntegration:
    @pytest.mark.asyncio
    async def test_status_transitions(self, async_session: AsyncSession, repo):
        record = await repo.create(
            async_session,
            {
                "creator_id": CREATOR_ID,
                "input_type": ContentInputType.SCRIPT,
                "input_text": " ".join(["word"] * 100),
            },
        )
        await async_session.commit()

        # PENDING → PROCESSING
        updated = await repo.update_assembly_status(
            async_session, record.content_item_id, AssemblyStatus.PROCESSING
        )
        await async_session.commit()
        assert updated.assembly_status == AssemblyStatus.PROCESSING

        # PROCESSING → COMPLETED
        updated = await repo.update_assembly_status(
            async_session,
            record.content_item_id,
            AssemblyStatus.COMPLETED,
            extra_fields={"video_draft_url": "s3://test/video.mp4"},
        )
        await async_session.commit()
        assert updated.assembly_status == AssemblyStatus.COMPLETED
        assert updated.video_draft_url == "s3://test/video.mp4"


class TestVersionHistoryIntegration:
    @pytest.mark.asyncio
    async def test_append_multiple_entries(self, async_session: AsyncSession, repo):
        record = await repo.create(
            async_session,
            {
                "creator_id": CREATOR_ID,
                "input_type": ContentInputType.SCRIPT,
                "input_text": " ".join(["word"] * 100),
            },
        )
        await async_session.commit()

        entry1 = {
            "version_id": str(uuid.uuid4()),
            "change_type": "pacing_adjustment",
            "changed_fields": {"scene_id": "s1", "old_pacing": 1.0, "new_pacing": 2.0},
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "changed_by": str(CREATOR_ID),
        }
        result = await repo.append_version_history(
            async_session, record.content_item_id, CREATOR_ID, entry1
        )
        await async_session.commit()
        assert len(result.version_history) == 1

        entry2 = {
            "version_id": str(uuid.uuid4()),
            "change_type": "visual_swap",
            "changed_fields": {"scene_id": "s1"},
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "changed_by": str(CREATOR_ID),
        }
        result = await repo.append_version_history(
            async_session, record.content_item_id, CREATOR_ID, entry2
        )
        await async_session.commit()
        assert len(result.version_history) == 2
        assert result.version_history[0]["change_type"] == "pacing_adjustment"
        assert result.version_history[1]["change_type"] == "visual_swap"


class TestListByCreatorIntegration:
    @pytest.mark.asyncio
    async def test_pagination_and_filtering(self, async_session: AsyncSession, repo):
        # Create items with different statuses
        for i in range(5):
            await repo.create(
                async_session,
                {
                    "creator_id": CREATOR_ID,
                    "input_type": ContentInputType.SCRIPT,
                    "input_text": " ".join(["word"] * 100),
                },
            )
        await async_session.commit()

        # Test pagination
        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, offset=0, limit=3
        )
        assert len(records) == 3
        assert total >= 5

        # Test creator scoping
        records, total = await repo.list_by_creator(
            async_session, OTHER_CREATOR_ID
        )
        assert total == 0

    @pytest.mark.asyncio
    async def test_sorting(self, async_session: AsyncSession, repo):
        for _ in range(3):
            await repo.create(
                async_session,
                {
                    "creator_id": CREATOR_ID,
                    "input_type": ContentInputType.TOPIC_PROMPT,
                    "input_text": " ".join(["mot"] * 30),
                },
            )
        await async_session.commit()

        records_desc, _ = await repo.list_by_creator(
            async_session, CREATOR_ID, sort_order="desc"
        )
        records_asc, _ = await repo.list_by_creator(
            async_session, CREATOR_ID, sort_order="asc"
        )
        if len(records_desc) > 1:
            assert records_desc[0].created_at >= records_desc[-1].created_at
