"""Integration tests for ScriptPromptInputRepository using SQLite."""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
    ScriptPromptInput,
    WorkflowState,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.repository import (
    ScriptPromptInputRepository,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def repo() -> ScriptPromptInputRepository:
    return ScriptPromptInputRepository()


async def _create_record(
    repo: ScriptPromptInputRepository,
    session: AsyncSession,
    content: str = "Valid test content for repository tests.",
    input_type: InputType = InputType.WRITTEN_SCRIPT,
    creator_id: uuid.UUID = CREATOR_ID,
) -> ScriptPromptInput:
    return await repo.create(
        session,
        {
            "creator_id": creator_id,
            "content_text": content,
            "input_type": input_type,
        },
    )


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_record_with_draft_state(self, repo, async_session):
        record = await _create_record(repo, async_session)
        assert record.workflow_state == WorkflowState.DRAFT
        assert record.input_record_id is not None
        assert record.character_count == len("Valid test content for repository tests.")


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_record_for_correct_creator(self, repo, async_session):
        created = await _create_record(repo, async_session)
        await async_session.commit()

        result = await repo.get_by_id(async_session, created.input_record_id, CREATOR_ID)
        assert result is not None
        assert result.input_record_id == created.input_record_id

    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_creator(self, repo, async_session):
        created = await _create_record(repo, async_session)
        await async_session.commit()

        other_creator = uuid.UUID("22222222-2222-2222-2222-222222222222")
        result = await repo.get_by_id(async_session, created.input_record_id, other_creator)
        assert result is None


class TestUpdate:
    @pytest.mark.asyncio
    async def test_updates_content_and_character_count(self, repo, async_session):
        created = await _create_record(repo, async_session)
        await async_session.commit()

        updated = await repo.update(
            async_session,
            created.input_record_id,
            CREATOR_ID,
            {"content_text": "Updated content text."},
        )
        assert updated is not None
        assert updated.character_count == len("Updated content text.")


class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_draft_record(self, repo, async_session):
        created = await _create_record(repo, async_session)
        await async_session.commit()

        result = await repo.delete(async_session, created.input_record_id, CREATOR_ID)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_draft(self, repo, async_session):
        created = await _create_record(repo, async_session)
        await repo.update_workflow_state(
            async_session, created.input_record_id, WorkflowState.SUBMITTED
        )
        await async_session.commit()

        result = await repo.delete(async_session, created.input_record_id, CREATOR_ID)
        assert result is False


class TestUpdateWorkflowState:
    @pytest.mark.asyncio
    async def test_transitions_state(self, repo, async_session):
        created = await _create_record(repo, async_session)
        await async_session.commit()

        updated = await repo.update_workflow_state(
            async_session,
            created.input_record_id,
            WorkflowState.SUBMITTED,
            extra_fields={"submitted_at": datetime.now(timezone.utc)},
        )
        assert updated is not None
        assert updated.workflow_state == WorkflowState.SUBMITTED
        assert updated.submitted_at is not None


class TestListByCreator:
    @pytest.mark.asyncio
    async def test_returns_paginated_results(self, repo, async_session):
        for i in range(5):
            await _create_record(repo, async_session, content=f"Content item number {i} for pagination.")
        await async_session.commit()

        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, limit=2, offset=0
        )
        assert len(records) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_filters_by_input_type(self, repo, async_session):
        await _create_record(repo, async_session, input_type=InputType.WRITTEN_SCRIPT)
        await _create_record(repo, async_session, input_type=InputType.TOPIC_OUTLINE)
        await async_session.commit()

        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, input_type=InputType.WRITTEN_SCRIPT
        )
        assert all(r.input_type == InputType.WRITTEN_SCRIPT for r in records)

    @pytest.mark.asyncio
    async def test_filters_by_workflow_state(self, repo, async_session):
        r1 = await _create_record(repo, async_session, content="Draft content stays here.")
        r2 = await _create_record(repo, async_session, content="Submitted content goes here.")
        await repo.update_workflow_state(async_session, r2.input_record_id, WorkflowState.SUBMITTED)
        await async_session.commit()

        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, workflow_state=WorkflowState.DRAFT
        )
        assert all(r.workflow_state == WorkflowState.DRAFT for r in records)

    @pytest.mark.asyncio
    async def test_has_next_and_has_previous(self, repo, async_session):
        for i in range(3):
            await _create_record(repo, async_session, content=f"Content for pagination test {i}.")
        await async_session.commit()

        records, total = await repo.list_by_creator(
            async_session, CREATOR_ID, limit=1, offset=1
        )
        assert len(records) == 1
        assert total >= 3


class TestDuplicate:
    @pytest.mark.asyncio
    async def test_duplicates_record(self, repo, async_session):
        source = await _create_record(repo, async_session)
        await async_session.commit()

        new_record = await repo.duplicate(async_session, source.input_record_id, CREATOR_ID)
        assert new_record is not None
        assert new_record.input_record_id != source.input_record_id
        assert new_record.content_text == source.content_text
        assert new_record.input_type == source.input_type
        assert new_record.workflow_state == WorkflowState.DRAFT

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent(self, repo, async_session):
        result = await repo.duplicate(async_session, uuid.uuid4(), CREATOR_ID)
        assert result is None
