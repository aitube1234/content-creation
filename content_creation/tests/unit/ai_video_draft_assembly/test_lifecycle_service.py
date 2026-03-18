"""Unit tests for LifecycleService (FR-25 to FR-28)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    ContentItemNotFoundError,
    LifecycleServiceUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    ContentItem,
    LifecycleState,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.lifecycle_service import (
    LifecycleService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_item(**overrides) -> MagicMock:
    item = MagicMock(spec=ContentItem)
    item.content_item_id = overrides.get("content_item_id", uuid.uuid4())
    item.creator_id = CREATOR_ID
    item.lifecycle_state = overrides.get("lifecycle_state", LifecycleState.DRAFT)
    return item


class TestRegisterDraft:
    """FR-25, FR-26: Draft registration in lifecycle management."""

    @pytest.fixture
    def service(self):
        return LifecycleService(
            repository=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_register_draft_success(self, service):
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.lifecycle_client.register_draft = AsyncMock(return_value=True)
        session = AsyncMock()

        result = await service.register_draft(
            session, item.content_item_id, CREATOR_ID
        )
        assert result is not None
        service.lifecycle_client.register_draft.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_draft_service_unavailable(self, service):
        """FR-27: Block creation if lifecycle service unavailable."""
        item = _make_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.lifecycle_client.register_draft = AsyncMock(
            side_effect=LifecycleServiceUnavailableError(
                message="Service unavailable"
            )
        )
        session = AsyncMock()

        with pytest.raises(LifecycleServiceUnavailableError):
            await service.register_draft(
                session, item.content_item_id, CREATOR_ID
            )

    @pytest.mark.asyncio
    async def test_register_draft_not_found(self, service):
        service.repository.get_by_id = AsyncMock(return_value=None)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.register_draft(session, uuid.uuid4(), CREATOR_ID)


class TestTransitionToPrePublish:
    """Test lifecycle state transition."""

    @pytest.fixture
    def service(self):
        return LifecycleService(
            repository=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_transition_from_draft(self, service):
        item = _make_item(lifecycle_state=LifecycleState.DRAFT)
        service.repository.get_by_id = AsyncMock(return_value=item)
        service.repository.update = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.transition_to_pre_publish(
            session, item.content_item_id, CREATOR_ID
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_transition_from_non_draft(self, service):
        item = _make_item(lifecycle_state=LifecycleState.PUBLISHED)
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.transition_to_pre_publish(
                session, item.content_item_id, CREATOR_ID
            )


class TestCheckAvailability:
    """FR-27: Service availability check."""

    @pytest.fixture
    def service(self):
        return LifecycleService(
            repository=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_available(self, service):
        service.lifecycle_client.check_availability = AsyncMock(return_value=True)
        assert await service.check_service_availability() is True

    @pytest.mark.asyncio
    async def test_unavailable(self, service):
        service.lifecycle_client.check_availability = AsyncMock(return_value=False)
        assert await service.check_service_availability() is False
