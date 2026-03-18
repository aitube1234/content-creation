"""Unit tests for DraftLifecycleService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.draft_lifecycle_service import (
    DraftLifecycleService,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ReportStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    ContributorAccessDeniedError,
    InvalidLifecycleTransitionError,
    OriginalityCheckTimeoutError,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CONTRIBUTOR_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def mock_draft_repo():
    return AsyncMock()


@pytest.fixture
def mock_report_repo():
    return AsyncMock()


@pytest.fixture
def mock_originality_service():
    return AsyncMock()


@pytest.fixture
def mock_thumbnail_service():
    return AsyncMock()


@pytest.fixture
def service(mock_draft_repo, mock_report_repo, mock_originality_service, mock_thumbnail_service):
    return DraftLifecycleService(
        draft_repository=mock_draft_repo,
        report_repository=mock_report_repo,
        originality_service=mock_originality_service,
        thumbnail_service=mock_thumbnail_service,
    )


@pytest.mark.asyncio
async def test_initiate_pre_publish_success(service, mock_draft_repo, mock_originality_service, mock_thumbnail_service):
    """Test successful Draft-to-Pre-Publish transition initiation."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft.lifecycle_state = LifecycleState.DRAFT
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_report = MagicMock()
    mock_originality_service.initiate_check.return_value = mock_report

    session = AsyncMock()
    status, report = await service.initiate_pre_publish_transition(
        session, content_item_id, CREATOR_ID,
    )

    assert status == "awaiting_confirmation"
    assert report == mock_report
    mock_thumbnail_service.auto_select_default.assert_called_once()


@pytest.mark.asyncio
async def test_initiate_pre_publish_only_lead_creator(service, mock_draft_repo):
    """Test only lead creator can initiate Draft-to-Pre-Publish transition."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft.lifecycle_state = LifecycleState.DRAFT
    mock_draft_repo.get_by_id.return_value = mock_draft

    session = AsyncMock()
    with pytest.raises(ContributorAccessDeniedError):
        await service.initiate_pre_publish_transition(
            session, content_item_id, CONTRIBUTOR_ID,
        )


@pytest.mark.asyncio
async def test_initiate_pre_publish_not_draft_state(service, mock_draft_repo):
    """Test transition fails from non-Draft state."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft.lifecycle_state = LifecycleState.PRE_PUBLISH
    mock_draft_repo.get_by_id.return_value = mock_draft

    session = AsyncMock()
    with pytest.raises(InvalidLifecycleTransitionError):
        await service.initiate_pre_publish_transition(
            session, content_item_id, CREATOR_ID,
        )


@pytest.mark.asyncio
async def test_initiate_pre_publish_timeout(service, mock_draft_repo, mock_originality_service, mock_thumbnail_service):
    """Test timeout returns timeout status and Draft state retained."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft.lifecycle_state = LifecycleState.DRAFT
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_originality_service.initiate_check.side_effect = OriginalityCheckTimeoutError(
        message="Timeout",
    )

    session = AsyncMock()
    status, report = await service.initiate_pre_publish_transition(
        session, content_item_id, CREATOR_ID,
    )

    assert status == "timeout"
    assert report is None


@pytest.mark.asyncio
async def test_confirm_pre_publish_success(service, mock_draft_repo, mock_report_repo):
    """Test Pre-Publish confirmation after reviewing originality report."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft.lifecycle_state = LifecycleState.DRAFT
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_report = MagicMock()
    mock_report.report_status = ReportStatus.COMPLETED
    mock_report_repo.get_by_content_item_id.return_value = mock_report

    mock_updated = MagicMock()
    mock_updated.lifecycle_state = LifecycleState.PRE_PUBLISH
    mock_draft_repo.update.return_value = mock_updated

    session = AsyncMock()
    result = await service.confirm_pre_publish(session, content_item_id, CREATOR_ID)

    assert result.lifecycle_state == LifecycleState.PRE_PUBLISH
    mock_draft_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_pre_publish_without_report(service, mock_draft_repo, mock_report_repo):
    """Test confirmation withheld until report returned."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft.lifecycle_state = LifecycleState.DRAFT
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_report_repo.get_by_content_item_id.return_value = None

    session = AsyncMock()
    with pytest.raises(InvalidLifecycleTransitionError, match="completed originality report"):
        await service.confirm_pre_publish(session, content_item_id, CREATOR_ID)


@pytest.mark.asyncio
async def test_retry_originality_success(service, mock_draft_repo, mock_originality_service):
    """Test retry originality check after timeout."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_report = MagicMock()
    mock_originality_service.retry_check.return_value = mock_report

    session = AsyncMock()
    status, report = await service.retry_originality(session, content_item_id, CREATOR_ID)

    assert status == "awaiting_confirmation"
    assert report == mock_report
