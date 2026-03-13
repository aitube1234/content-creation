"""Main service orchestration layer for script prompt ingestion."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.exceptions import (
    DuplicateGenerationRequestError,
    InputNotDeletableError,
    InputRecordNotFoundError,
    InputTypeNotChangeableError,
    InvalidStateTransitionError,
    PipelineUnavailableError,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
    ScriptPromptInput,
    WorkflowState,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.pipeline_client import (
    VideoGenerationPipelineClient,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.repository import (
    ScriptPromptInputRepository,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.state_machine import (
    InputLifecycleStateMachine,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.validation_service import (
    InputValidationService,
)

logger = logging.getLogger(__name__)


class ScriptPromptIngestionService:
    """Orchestrates all script prompt ingestion operations."""

    def __init__(
        self,
        repository: ScriptPromptInputRepository | None = None,
        validation_service: InputValidationService | None = None,
        state_machine: InputLifecycleStateMachine | None = None,
        pipeline_client: VideoGenerationPipelineClient | None = None,
    ) -> None:
        self.repository = repository or ScriptPromptInputRepository()
        self.validation_service = validation_service or InputValidationService()
        self.state_machine = state_machine or InputLifecycleStateMachine()
        self.pipeline_client = pipeline_client or VideoGenerationPipelineClient()

    async def create_input_draft(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        content_text: str,
        input_type: InputType | None = None,
    ) -> ScriptPromptInput:
        """Create a new input record with state=Draft."""
        record = await self.repository.create(
            session,
            {
                "creator_id": creator_id,
                "content_text": content_text,
                "input_type": input_type,
            },
        )
        logger.info(
            "Created draft input %s for creator %s",
            record.input_record_id,
            creator_id,
        )
        return record

    async def update_input_draft(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
        content_text: str | None = None,
        input_type: InputType | None = None,
    ) -> ScriptPromptInput:
        """Update content and/or type on a Draft record."""
        record = await self._get_record_or_raise(session, input_record_id, creator_id)

        if record.workflow_state != WorkflowState.DRAFT:
            if input_type is not None and not self.state_machine.can_change_type(record.workflow_state):
                raise InputTypeNotChangeableError(
                    message=f"Cannot change input type when record is in '{record.workflow_state.value}' state."
                )
            raise InvalidStateTransitionError(
                message=f"Cannot update record in '{record.workflow_state.value}' state. Only Draft records are editable."
            )

        update_data: dict = {}
        if content_text is not None:
            update_data["content_text"] = content_text
        if input_type is not None:
            update_data["input_type"] = input_type
        update_data["validation_errors"] = None

        updated = await self.repository.update(
            session, input_record_id, creator_id, update_data
        )
        if updated is None:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found."
            )
        logger.info("Updated draft input %s", input_record_id)
        return updated

    async def delete_input_draft(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> None:
        """Delete a Draft record."""
        record = await self._get_record_or_raise(session, input_record_id, creator_id)

        if not self.state_machine.can_delete(record.workflow_state):
            raise InputNotDeletableError(
                message=f"Cannot delete record in '{record.workflow_state.value}' state. Only Draft records can be deleted."
            )

        deleted = await self.repository.delete(session, input_record_id, creator_id)
        if not deleted:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found."
            )
        logger.info("Deleted draft input %s", input_record_id)

    async def submit_input(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput:
        """Submit a Draft for validation and generation initiation."""
        record = await self._get_record_or_raise(session, input_record_id, creator_id)

        if record.workflow_state == WorkflowState.GENERATION_INITIATED:
            raise DuplicateGenerationRequestError(
                message="Generation has already been initiated for this record."
            )

        if not self.state_machine.can_submit(record.workflow_state):
            raise InvalidStateTransitionError(
                message=f"Cannot submit record in '{record.workflow_state.value}' state."
            )

        # Transition to Submitted
        self.state_machine.transition(record.workflow_state, WorkflowState.SUBMITTED)
        await self.repository.update_workflow_state(
            session,
            input_record_id,
            WorkflowState.SUBMITTED,
            extra_fields={"submitted_at": datetime.now(timezone.utc)},
        )

        # Validate
        validation_result = self.validation_service.validate(
            record.content_text, record.input_type
        )

        if not validation_result.is_valid:
            error_messages = [e.message for e in validation_result.errors]
            self.state_machine.transition(
                WorkflowState.SUBMITTED, WorkflowState.VALIDATION_FAILED
            )
            updated = await self.repository.update_workflow_state(
                session,
                input_record_id,
                WorkflowState.VALIDATION_FAILED,
                extra_fields={"validation_errors": error_messages},
            )
            logger.info(
                "Validation failed for input %s: %s",
                input_record_id,
                error_messages,
            )
            if updated is None:
                raise InputRecordNotFoundError(
                    message=f"Input record '{input_record_id}' not found."
                )
            return updated

        # Submit to pipeline
        try:
            generation_request_id = await self.pipeline_client.submit_for_generation(
                input_record_id, record.input_type, record.content_text
            )
        except PipelineUnavailableError:
            logger.error(
                "Pipeline unavailable for input %s; retaining Submitted state",
                input_record_id,
            )
            # Retain Submitted state so retry is possible
            updated = await self.repository.update_workflow_state(
                session, input_record_id, WorkflowState.SUBMITTED
            )
            if updated is None:
                raise InputRecordNotFoundError(
                    message=f"Input record '{input_record_id}' not found."
                )
            raise

        # Transition to GenerationInitiated
        self.state_machine.transition(
            WorkflowState.SUBMITTED, WorkflowState.GENERATION_INITIATED
        )
        updated = await self.repository.update_workflow_state(
            session,
            input_record_id,
            WorkflowState.GENERATION_INITIATED,
            extra_fields={"generation_request_id": generation_request_id},
        )
        logger.info(
            "Generation initiated for input %s with request %s",
            input_record_id,
            generation_request_id,
        )
        if updated is None:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found."
            )
        return updated

    async def revert_to_draft(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput:
        """Revert a ValidationFailed record back to Draft."""
        record = await self._get_record_or_raise(session, input_record_id, creator_id)

        self.state_machine.transition(record.workflow_state, WorkflowState.DRAFT)
        updated = await self.repository.update_workflow_state(
            session,
            input_record_id,
            WorkflowState.DRAFT,
            extra_fields={"validation_errors": None},
        )
        if updated is None:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found."
            )
        logger.info("Reverted input %s to Draft", input_record_id)
        return updated

    async def retry_generation(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput:
        """Retry pipeline submission for a Submitted record."""
        record = await self._get_record_or_raise(session, input_record_id, creator_id)

        if record.workflow_state == WorkflowState.GENERATION_INITIATED:
            raise DuplicateGenerationRequestError(
                message="Generation has already been initiated for this record."
            )

        if record.workflow_state != WorkflowState.SUBMITTED:
            raise InvalidStateTransitionError(
                message=f"Cannot retry generation for record in '{record.workflow_state.value}' state. Record must be in 'submitted' state."
            )

        generation_request_id = await self.pipeline_client.submit_for_generation(
            input_record_id, record.input_type, record.content_text
        )

        self.state_machine.transition(
            WorkflowState.SUBMITTED, WorkflowState.GENERATION_INITIATED
        )
        updated = await self.repository.update_workflow_state(
            session,
            input_record_id,
            WorkflowState.GENERATION_INITIATED,
            extra_fields={"generation_request_id": generation_request_id},
        )
        if updated is None:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found."
            )
        logger.info(
            "Retry generation initiated for input %s with request %s",
            input_record_id,
            generation_request_id,
        )
        return updated

    async def get_input_record(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput:
        """Fetch a single record by ID scoped to the authenticated creator."""
        return await self._get_record_or_raise(session, input_record_id, creator_id)

    async def list_input_history(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        input_type: InputType | None = None,
        workflow_state: WorkflowState | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScriptPromptInput], int]:
        """Return paginated, filtered, sorted history list."""
        offset = (page - 1) * page_size
        return await self.repository.list_by_creator(
            session,
            creator_id,
            input_type=input_type,
            workflow_state=workflow_state,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=page_size,
        )

    async def duplicate_input_record(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput:
        """Create a new Draft copy of an existing record."""
        await self._get_record_or_raise(session, input_record_id, creator_id)
        new_record = await self.repository.duplicate(
            session, input_record_id, creator_id
        )
        if new_record is None:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found."
            )
        logger.info(
            "Duplicated input %s as %s",
            input_record_id,
            new_record.input_record_id,
        )
        return new_record

    async def _get_record_or_raise(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput:
        """Fetch a record or raise InputRecordNotFoundError."""
        record = await self.repository.get_by_id(session, input_record_id, creator_id)
        if record is None:
            raise InputRecordNotFoundError(
                message=f"Input record '{input_record_id}' not found for creator '{creator_id}'."
            )
        return record
