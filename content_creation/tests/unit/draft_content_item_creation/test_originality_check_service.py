"""Unit tests for OriginalityCheckService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ReportStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    DraftContentItemNotFoundError,
    OriginalityCheckTimeoutError,
    OriginalityEngineUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.originality_check_service import (
    OriginalityCheckService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def mock_draft_repo():
    return AsyncMock()


@pytest.fixture
def mock_report_repo():
    return AsyncMock()


@pytest.fixture
def mock_engine_client():
    return AsyncMock()


@pytest.fixture
def service(mock_draft_repo, mock_report_repo, mock_engine_client):
    return OriginalityCheckService(
        draft_repository=mock_draft_repo,
        report_repository=mock_report_repo,
        engine_client=mock_engine_client,
    )


@pytest.mark.asyncio
async def test_initiate_check_success(service, mock_draft_repo, mock_report_repo, mock_engine_client):
    """Test successful originality engine invocation and report storage."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_engine_client.check_originality.return_value = {
        "duplicate_risk_score": 25,
        "similar_content_items": ["item1"],
        "differentiation_recommendations": ["Be more unique"],
    }

    mock_report = MagicMock()
    mock_report.originality_report_id = uuid.uuid4()
    mock_report_repo.create.return_value = mock_report
    mock_draft_repo.update.return_value = MagicMock()

    session = AsyncMock()
    result = await service.initiate_check(session, content_item_id, CREATOR_ID)

    assert result == mock_report
    # Verify report was stored with correct status
    report_data = mock_report_repo.create.call_args[0][1]
    assert report_data["report_status"] == ReportStatus.COMPLETED
    assert report_data["duplicate_risk_score"] == 25


@pytest.mark.asyncio
async def test_initiate_check_timeout(service, mock_draft_repo, mock_report_repo, mock_engine_client):
    """Test SLA timeout detection stores timeout report and raises."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_engine_client.check_originality.side_effect = OriginalityCheckTimeoutError(
        message="Timed out",
    )
    mock_report_repo.create.return_value = MagicMock()

    session = AsyncMock()
    with pytest.raises(OriginalityCheckTimeoutError):
        await service.initiate_check(session, content_item_id, CREATOR_ID)

    # Verify timeout report was stored
    report_data = mock_report_repo.create.call_args[0][1]
    assert report_data["report_status"] == ReportStatus.TIMEOUT


@pytest.mark.asyncio
async def test_initiate_check_engine_unavailable(service, mock_draft_repo, mock_report_repo, mock_engine_client):
    """Test engine unavailability stores failed report and raises."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_engine_client.check_originality.side_effect = OriginalityEngineUnavailableError(
        message="Engine down",
    )
    mock_report_repo.create.return_value = MagicMock()

    session = AsyncMock()
    with pytest.raises(OriginalityEngineUnavailableError):
        await service.initiate_check(session, content_item_id, CREATOR_ID)

    report_data = mock_report_repo.create.call_args[0][1]
    assert report_data["report_status"] == ReportStatus.FAILED


@pytest.mark.asyncio
async def test_initiate_check_draft_not_found(service, mock_draft_repo):
    """Test initiate_check raises when draft not found."""
    mock_draft_repo.get_by_id.return_value = None

    session = AsyncMock()
    with pytest.raises(DraftContentItemNotFoundError):
        await service.initiate_check(session, uuid.uuid4(), CREATOR_ID)


@pytest.mark.asyncio
async def test_retry_check_delegates_to_initiate(service, mock_draft_repo, mock_report_repo, mock_engine_client):
    """Test retry_check calls initiate_check."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft_repo.get_by_id.return_value = mock_draft
    mock_engine_client.check_originality.return_value = {
        "duplicate_risk_score": 10,
        "similar_content_items": [],
        "differentiation_recommendations": [],
    }
    mock_report = MagicMock()
    mock_report_repo.create.return_value = mock_report
    mock_draft_repo.update.return_value = MagicMock()

    session = AsyncMock()
    result = await service.retry_check(session, content_item_id, CREATOR_ID)
    assert result == mock_report


@pytest.mark.asyncio
async def test_advisory_only_any_score_proceeds(service, mock_draft_repo, mock_report_repo, mock_engine_client):
    """Test transition proceeds regardless of duplicate_risk_score (advisory only)."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft_repo.get_by_id.return_value = mock_draft

    # High duplicate risk score - should still succeed
    mock_engine_client.check_originality.return_value = {
        "duplicate_risk_score": 95,
        "similar_content_items": ["item1", "item2"],
        "differentiation_recommendations": [],
    }
    mock_report = MagicMock()
    mock_report_repo.create.return_value = mock_report
    mock_draft_repo.update.return_value = MagicMock()

    session = AsyncMock()
    result = await service.initiate_check(session, content_item_id, CREATOR_ID)

    # Report stored successfully regardless of score
    assert result == mock_report
    report_data = mock_report_repo.create.call_args[0][1]
    assert report_data["report_status"] == ReportStatus.COMPLETED
