"""Unit tests for VersionHistoryService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    ContributionStatus,
    VersionEventType,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.exceptions import (
    ContributorAccessDeniedError,
    DraftContentItemNotFoundError,
    VersionEntryNotFoundError,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.version_history_service import (
    VersionHistoryService,
)

CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CONTRIBUTOR_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def mock_draft_repo():
    return AsyncMock()


@pytest.fixture
def mock_version_history_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_draft_repo, mock_version_history_repo):
    return VersionHistoryService(
        draft_repository=mock_draft_repo,
        version_history_repository=mock_version_history_repo,
    )


@pytest.mark.asyncio
async def test_create_entry_all_event_types(service, mock_version_history_repo):
    """Test entry creation for each of the six tracked event types."""
    session = AsyncMock()
    content_item_id = uuid.uuid4()
    mock_version_history_repo.create.return_value = MagicMock()

    for event_type in VersionEventType:
        await service.create_entry(
            session,
            content_item_id=content_item_id,
            event_type=event_type,
            actor_account_id=CREATOR_ID,
            actor_role=ActorRole.LEAD_CREATOR,
            event_payload={"detail": event_type.value},
        )

    assert mock_version_history_repo.create.call_count == 6


@pytest.mark.asyncio
async def test_list_entries_lead_creator_sees_all(service, mock_draft_repo, mock_version_history_repo):
    """Test lead creator sees all version history entries."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft
    mock_version_history_repo.list_by_content_item.return_value = ([], 0)

    session = AsyncMock()
    await service.list_entries(session, content_item_id, requester_id=CREATOR_ID)

    # Lead creator should not have actor_account_id filter
    call_kwargs = mock_version_history_repo.list_by_content_item.call_args
    assert call_kwargs[1]["actor_account_id"] is None


@pytest.mark.asyncio
async def test_list_entries_contributor_sees_own_only(service, mock_draft_repo, mock_version_history_repo):
    """Test contributor only sees their own entries."""
    content_item_id = uuid.uuid4()
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft
    mock_version_history_repo.list_by_content_item.return_value = ([], 0)

    session = AsyncMock()
    await service.list_entries(session, content_item_id, requester_id=CONTRIBUTOR_ID)

    # Contributor should have actor_account_id filter set
    call_kwargs = mock_version_history_repo.list_by_content_item.call_args
    assert call_kwargs[1]["actor_account_id"] == CONTRIBUTOR_ID


@pytest.mark.asyncio
async def test_accept_contribution(service, mock_draft_repo, mock_version_history_repo):
    """Test lead creator accepts a contributor contribution."""
    content_item_id = uuid.uuid4()
    version_entry_id = uuid.uuid4()

    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_entry = MagicMock()
    mock_entry.content_item_id = content_item_id
    mock_version_history_repo.get_by_id.return_value = mock_entry
    mock_version_history_repo.update_contribution_status.return_value = mock_entry

    session = AsyncMock()
    result = await service.accept_contribution(
        session, content_item_id, version_entry_id, CREATOR_ID,
    )

    mock_version_history_repo.update_contribution_status.assert_called_once_with(
        session, version_entry_id, ContributionStatus.ACCEPTED,
    )


@pytest.mark.asyncio
async def test_override_contribution(service, mock_draft_repo, mock_version_history_repo):
    """Test lead creator overrides a contributor contribution."""
    content_item_id = uuid.uuid4()
    version_entry_id = uuid.uuid4()

    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft

    mock_entry = MagicMock()
    mock_entry.content_item_id = content_item_id
    mock_version_history_repo.get_by_id.return_value = mock_entry
    mock_version_history_repo.update_contribution_status.return_value = mock_entry

    session = AsyncMock()
    await service.override_contribution(
        session, content_item_id, version_entry_id, CREATOR_ID,
    )

    mock_version_history_repo.update_contribution_status.assert_called_once_with(
        session, version_entry_id, ContributionStatus.OVERRIDDEN,
    )


@pytest.mark.asyncio
async def test_accept_contribution_access_denied(service, mock_draft_repo):
    """Test contributor cannot accept contributions."""
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft

    session = AsyncMock()
    with pytest.raises(ContributorAccessDeniedError):
        await service.accept_contribution(
            session, uuid.uuid4(), uuid.uuid4(), CONTRIBUTOR_ID,
        )


@pytest.mark.asyncio
async def test_accept_contribution_entry_not_found(service, mock_draft_repo, mock_version_history_repo):
    """Test accept fails when version entry not found."""
    mock_draft = MagicMock()
    mock_draft.lead_creator_account_id = CREATOR_ID
    mock_draft_repo.get_by_id.return_value = mock_draft
    mock_version_history_repo.get_by_id.return_value = None

    session = AsyncMock()
    with pytest.raises(VersionEntryNotFoundError):
        await service.accept_contribution(
            session, uuid.uuid4(), uuid.uuid4(), CREATOR_ID,
        )


@pytest.mark.asyncio
async def test_list_entries_draft_not_found(service, mock_draft_repo):
    """Test list_entries raises when draft not found."""
    mock_draft_repo.get_by_id.return_value = None

    session = AsyncMock()
    with pytest.raises(DraftContentItemNotFoundError):
        await service.list_entries(session, uuid.uuid4(), requester_id=CREATOR_ID)
