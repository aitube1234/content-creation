"""Unit tests for ScriptPromptIngestionService."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.exceptions import (
    DuplicateGenerationRequestError,
    InputNotDeletableError,
    InputRecordNotFoundError,
    InvalidStateTransitionError,
    PipelineUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
    ScriptPromptInput,
    WorkflowState,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.service import (
    ScriptPromptIngestionService,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.validation_service import (
    InputValidationService,
    ValidationResult,
)


CREATOR_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_record(
    state: WorkflowState = WorkflowState.DRAFT,
    input_type: InputType = InputType.WRITTEN_SCRIPT,
    content_text: str = "Sample content text for testing purposes.",
) -> ScriptPromptInput:
    """Create a mock ScriptPromptInput record."""
    record = MagicMock(spec=ScriptPromptInput)
    record.input_record_id = uuid.uuid4()
    record.creator_id = CREATOR_ID
    record.input_type = input_type
    record.content_text = content_text
    record.workflow_state = state
    record.validation_errors = None
    record.generation_request_id = None
    record.created_at = datetime.now(timezone.utc)
    record.last_modified_at = datetime.now(timezone.utc)
    record.submitted_at = None
    record.character_count = len(content_text)
    return record


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    client = AsyncMock()
    client.submit_for_generation = AsyncMock(return_value=uuid.uuid4())
    return client


@pytest.fixture
def mock_validation() -> MagicMock:
    svc = MagicMock(spec=InputValidationService)
    svc.validate = MagicMock(return_value=ValidationResult(is_valid=True, errors=[]))
    return svc


@pytest.fixture
def svc(mock_repo, mock_pipeline, mock_validation) -> ScriptPromptIngestionService:
    return ScriptPromptIngestionService(
        repository=mock_repo,
        validation_service=mock_validation,
        pipeline_client=mock_pipeline,
    )


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


class TestCreateInputDraft:
    @pytest.mark.asyncio
    async def test_creates_draft_with_correct_data(self, svc, mock_repo, session):
        draft = _make_record()
        mock_repo.create.return_value = draft

        result = await svc.create_input_draft(
            session, CREATOR_ID, "Sample content text for testing purposes."
        )

        mock_repo.create.assert_called_once()
        call_data = mock_repo.create.call_args[0][1]
        assert call_data["creator_id"] == CREATOR_ID
        assert call_data["content_text"] == "Sample content text for testing purposes."
        assert result == draft

    @pytest.mark.asyncio
    async def test_creates_draft_with_input_type(self, svc, mock_repo, session):
        draft = _make_record(input_type=InputType.TOPIC_OUTLINE)
        mock_repo.create.return_value = draft

        result = await svc.create_input_draft(
            session, CREATOR_ID, "content", input_type=InputType.TOPIC_OUTLINE
        )

        call_data = mock_repo.create.call_args[0][1]
        assert call_data["input_type"] == InputType.TOPIC_OUTLINE


class TestUpdateInputDraft:
    @pytest.mark.asyncio
    async def test_updates_draft_record(self, svc, mock_repo, session):
        draft = _make_record()
        mock_repo.get_by_id.return_value = draft
        updated = _make_record()
        mock_repo.update.return_value = updated

        result = await svc.update_input_draft(
            session, draft.input_record_id, CREATOR_ID, content_text="updated text"
        )

        mock_repo.update.assert_called_once()
        assert result == updated

    @pytest.mark.asyncio
    async def test_rejects_update_on_non_draft(self, svc, mock_repo, session):
        record = _make_record(state=WorkflowState.SUBMITTED)
        mock_repo.get_by_id.return_value = record

        with pytest.raises(InvalidStateTransitionError):
            await svc.update_input_draft(
                session, record.input_record_id, CREATOR_ID, content_text="new"
            )

    @pytest.mark.asyncio
    async def test_clears_validation_errors_on_update(self, svc, mock_repo, session):
        draft = _make_record()
        mock_repo.get_by_id.return_value = draft
        mock_repo.update.return_value = draft

        await svc.update_input_draft(
            session, draft.input_record_id, CREATOR_ID, content_text="updated text"
        )

        call_data = mock_repo.update.call_args[1].get("data") or mock_repo.update.call_args[0][3]
        assert call_data.get("validation_errors") is None


class TestDeleteInputDraft:
    @pytest.mark.asyncio
    async def test_deletes_draft(self, svc, mock_repo, session):
        draft = _make_record()
        mock_repo.get_by_id.return_value = draft
        mock_repo.delete.return_value = True

        await svc.delete_input_draft(session, draft.input_record_id, CREATOR_ID)
        mock_repo.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_delete_on_generation_initiated(self, svc, mock_repo, session):
        record = _make_record(state=WorkflowState.GENERATION_INITIATED)
        mock_repo.get_by_id.return_value = record

        with pytest.raises(InputNotDeletableError):
            await svc.delete_input_draft(session, record.input_record_id, CREATOR_ID)


class TestSubmitInput:
    @pytest.mark.asyncio
    async def test_happy_path(self, svc, mock_repo, mock_pipeline, mock_validation, session):
        draft = _make_record()
        mock_repo.get_by_id.return_value = draft
        gen_id = uuid.uuid4()
        mock_pipeline.submit_for_generation.return_value = gen_id
        mock_validation.validate.return_value = ValidationResult(is_valid=True, errors=[])

        initiated = _make_record(state=WorkflowState.GENERATION_INITIATED)
        initiated.generation_request_id = gen_id
        mock_repo.update_workflow_state.return_value = initiated

        result = await svc.submit_input(session, draft.input_record_id, CREATOR_ID)

        mock_pipeline.submit_for_generation.assert_called_once()
        assert result == initiated

    @pytest.mark.asyncio
    async def test_validation_failure(self, svc, mock_repo, mock_pipeline, mock_validation, session):
        from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.schemas import (
            ValidationErrorDetail,
        )

        draft = _make_record()
        mock_repo.get_by_id.return_value = draft
        mock_validation.validate.return_value = ValidationResult(
            is_valid=False,
            errors=[ValidationErrorDetail(field="content_text", message="Too short", error_code="CONTENT_TOO_SHORT")],
        )
        failed = _make_record(state=WorkflowState.VALIDATION_FAILED)
        mock_repo.update_workflow_state.return_value = failed

        result = await svc.submit_input(session, draft.input_record_id, CREATOR_ID)

        mock_pipeline.submit_for_generation.assert_not_called()
        assert result == failed

    @pytest.mark.asyncio
    async def test_pipeline_failure(self, svc, mock_repo, mock_pipeline, mock_validation, session):
        draft = _make_record()
        mock_repo.get_by_id.return_value = draft
        mock_validation.validate.return_value = ValidationResult(is_valid=True, errors=[])
        mock_pipeline.submit_for_generation.side_effect = PipelineUnavailableError("unavailable")

        submitted = _make_record(state=WorkflowState.SUBMITTED)
        mock_repo.update_workflow_state.return_value = submitted

        with pytest.raises(PipelineUnavailableError):
            await svc.submit_input(session, draft.input_record_id, CREATOR_ID)


class TestRevertToDraft:
    @pytest.mark.asyncio
    async def test_reverts_validation_failed(self, svc, mock_repo, session):
        record = _make_record(state=WorkflowState.VALIDATION_FAILED)
        mock_repo.get_by_id.return_value = record
        reverted = _make_record(state=WorkflowState.DRAFT)
        mock_repo.update_workflow_state.return_value = reverted

        result = await svc.revert_to_draft(session, record.input_record_id, CREATOR_ID)
        assert result == reverted


class TestRetryGeneration:
    @pytest.mark.asyncio
    async def test_blocked_when_generation_initiated(self, svc, mock_repo, session):
        record = _make_record(state=WorkflowState.GENERATION_INITIATED)
        mock_repo.get_by_id.return_value = record

        with pytest.raises(DuplicateGenerationRequestError):
            await svc.retry_generation(session, record.input_record_id, CREATOR_ID)

    @pytest.mark.asyncio
    async def test_succeeds_for_submitted(self, svc, mock_repo, mock_pipeline, session):
        record = _make_record(state=WorkflowState.SUBMITTED)
        mock_repo.get_by_id.return_value = record
        gen_id = uuid.uuid4()
        mock_pipeline.submit_for_generation.return_value = gen_id
        initiated = _make_record(state=WorkflowState.GENERATION_INITIATED)
        mock_repo.update_workflow_state.return_value = initiated

        result = await svc.retry_generation(session, record.input_record_id, CREATOR_ID)
        assert result == initiated


class TestDuplicateInputRecord:
    @pytest.mark.asyncio
    async def test_duplicates_record(self, svc, mock_repo, session):
        source = _make_record()
        mock_repo.get_by_id.return_value = source
        new_record = _make_record()
        new_record.input_record_id = uuid.uuid4()
        mock_repo.duplicate.return_value = new_record

        result = await svc.duplicate_input_record(
            session, source.input_record_id, CREATOR_ID
        )

        mock_repo.duplicate.assert_called_once()
        assert result == new_record
