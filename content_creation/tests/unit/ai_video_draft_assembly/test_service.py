"""Unit tests for AssemblyService."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.exceptions import (
    AssemblyAlreadyProcessingError,
    AssemblyNotRetryableError,
    ContentItemNotFoundError,
    InputValidationError,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    AssemblyStatus,
    ContentInputType,
    ContentItem,
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.service import (
    AssemblyService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_content_item(**overrides) -> ContentItem:
    """Create a ContentItem with default values."""
    defaults = {
        "content_item_id": uuid.uuid4(),
        "creator_id": CREATOR_ID,
        "input_type": ContentInputType.SCRIPT,
        "input_text": " ".join(["word"] * 150),
        "input_locale": "fr",
        "lifecycle_state": LifecycleState.DRAFT,
        "assembly_status": AssemblyStatus.COMPLETED,
        "video_draft_url": "s3://test/draft/video.mp4",
        "scenes": [],
        "metadata_status": MetadataStatus.GENERATED,
        "ai_title": "Test",
        "ai_description": "Test Description",
        "ai_tags": ["test"],
        "ai_topic_cluster": "general",
        "thumbnail_options": [],
        "selected_thumbnail_url": None,
        "version_history": [],
        "word_count": 150,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    item = MagicMock(spec=ContentItem)
    for key, value in defaults.items():
        setattr(item, key, value)
    return item


class TestSubmitAssembly:
    """Tests for assembly submission."""

    @pytest.fixture
    def service(self):
        svc = AssemblyService(
            repository=AsyncMock(),
            input_service=MagicMock(),
            s3_client=AsyncMock(),
            metadata_engine_client=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )
        return svc

    @pytest.mark.asyncio
    async def test_validation_failure_raises(self, service):
        """Input that fails validation should raise InputValidationError."""
        from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.input_service import (
            InputValidationResult,
        )
        from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.schemas import (
            ValidationErrorDetail,
        )

        service.input_service.validate.return_value = InputValidationResult(
            is_valid=False,
            errors=[
                ValidationErrorDetail(
                    field="input_text",
                    message="Too short",
                    error_code="SCRIPT_TOO_SHORT",
                )
            ],
        )

        session = AsyncMock()
        with pytest.raises(InputValidationError):
            await service.submit_assembly(
                session, CREATOR_ID, ContentInputType.SCRIPT, "short"
            )


class TestRetryAssembly:
    """Tests for retry logic."""

    @pytest.fixture
    def service(self):
        svc = AssemblyService(
            repository=AsyncMock(),
            input_service=MagicMock(),
            s3_client=AsyncMock(),
            metadata_engine_client=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )
        return svc

    @pytest.mark.asyncio
    async def test_retry_already_processing(self, service):
        """Cannot retry an assembly that is already processing."""
        item = _make_content_item(assembly_status=AssemblyStatus.PROCESSING)
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        with pytest.raises(AssemblyAlreadyProcessingError):
            await service.retry_assembly(session, item.content_item_id, CREATOR_ID)

    @pytest.mark.asyncio
    async def test_retry_not_failed(self, service):
        """Cannot retry an assembly that is not in FAILED state."""
        item = _make_content_item(assembly_status=AssemblyStatus.PENDING)
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        with pytest.raises(AssemblyNotRetryableError):
            await service.retry_assembly(session, item.content_item_id, CREATOR_ID)

    @pytest.mark.asyncio
    async def test_retry_not_found(self, service):
        """Retry on non-existent item raises ContentItemNotFoundError."""
        service.repository.get_by_id = AsyncMock(return_value=None)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.retry_assembly(session, uuid.uuid4(), CREATOR_ID)


class TestGetContentItem:
    """Tests for getting content items."""

    @pytest.fixture
    def service(self):
        return AssemblyService(
            repository=AsyncMock(),
            input_service=MagicMock(),
            s3_client=AsyncMock(),
            metadata_engine_client=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_get_existing(self, service):
        item = _make_content_item()
        service.repository.get_by_id = AsyncMock(return_value=item)
        session = AsyncMock()

        result = await service.get_content_item(
            session, item.content_item_id, CREATOR_ID
        )
        assert result.content_item_id == item.content_item_id

    @pytest.mark.asyncio
    async def test_get_not_found(self, service):
        service.repository.get_by_id = AsyncMock(return_value=None)
        session = AsyncMock()

        with pytest.raises(ContentItemNotFoundError):
            await service.get_content_item(session, uuid.uuid4(), CREATOR_ID)


class TestListContentItems:
    """Tests for listing content items."""

    @pytest.fixture
    def service(self):
        return AssemblyService(
            repository=AsyncMock(),
            input_service=MagicMock(),
            s3_client=AsyncMock(),
            metadata_engine_client=AsyncMock(),
            lifecycle_client=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_list_returns_tuple(self, service):
        items = [_make_content_item(), _make_content_item()]
        service.repository.list_by_creator = AsyncMock(return_value=(items, 2))
        session = AsyncMock()

        result, total = await service.list_content_items(session, CREATOR_ID)
        assert total == 2
        assert len(result) == 2
