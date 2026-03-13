"""FastAPI router for script prompt ingestion endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.database import get_async_session
from backend.services.content_creation.utils.auth import get_current_creator_id
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
    WorkflowState,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.schemas import (
    CreateInputRequest,
    GenerationInitiatedResponse,
    InputRecordResponse,
    InputRecordSummaryResponse,
    PaginatedInputHistoryResponse,
    UpdateInputRequest,
)
from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.service import (
    ScriptPromptIngestionService,
)

router = APIRouter(
    prefix="/v1/script-prompt-inputs",
    tags=["Script Prompt Ingestion"],
)


def get_service() -> ScriptPromptIngestionService:
    """Dependency that provides the service instance."""
    return ScriptPromptIngestionService()


@router.post(
    "",
    response_model=InputRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_input(
    body: CreateInputRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> InputRecordResponse:
    """Create a new Draft input record."""
    record = await service.create_input_draft(
        session,
        creator_id=creator_id,
        content_text=body.content_text,
        input_type=body.input_type,
    )
    return InputRecordResponse.model_validate(record)


@router.get(
    "",
    response_model=PaginatedInputHistoryResponse,
)
async def list_inputs(
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    input_type: InputType | None = Query(default=None),
    workflow_state: WorkflowState | None = Query(default=None),
) -> PaginatedInputHistoryResponse:
    """List input history with pagination, filtering, and sorting."""
    records, total = await service.list_input_history(
        session,
        creator_id=creator_id,
        input_type=input_type,
        workflow_state=workflow_state,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    items = [InputRecordSummaryResponse.model_validate(r) for r in records]
    return PaginatedInputHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
        has_previous=page > 1,
    )


@router.get(
    "/{input_record_id}",
    response_model=InputRecordResponse,
)
async def get_input(
    input_record_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> InputRecordResponse:
    """Retrieve a single input record in full."""
    record = await service.get_input_record(session, input_record_id, creator_id)
    return InputRecordResponse.model_validate(record)


@router.patch(
    "/{input_record_id}",
    response_model=InputRecordResponse,
)
async def update_input(
    input_record_id: uuid.UUID,
    body: UpdateInputRequest,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> InputRecordResponse:
    """Update content and/or type on a Draft record."""
    record = await service.update_input_draft(
        session,
        input_record_id,
        creator_id,
        content_text=body.content_text,
        input_type=body.input_type,
    )
    return InputRecordResponse.model_validate(record)


@router.delete(
    "/{input_record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_input(
    input_record_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> None:
    """Delete a Draft input record."""
    await service.delete_input_draft(session, input_record_id, creator_id)


@router.post(
    "/{input_record_id}/submit",
    response_model=InputRecordResponse,
)
async def submit_input(
    input_record_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> InputRecordResponse:
    """Submit a Draft for validation and generation initiation."""
    record = await service.submit_input(session, input_record_id, creator_id)
    return InputRecordResponse.model_validate(record)


@router.post(
    "/{input_record_id}/revert",
    response_model=InputRecordResponse,
)
async def revert_input(
    input_record_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> InputRecordResponse:
    """Revert a ValidationFailed record back to Draft."""
    record = await service.revert_to_draft(session, input_record_id, creator_id)
    return InputRecordResponse.model_validate(record)


@router.post(
    "/{input_record_id}/retry-generation",
    response_model=GenerationInitiatedResponse,
)
async def retry_generation(
    input_record_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> GenerationInitiatedResponse:
    """Retry pipeline submission for a Submitted record."""
    record = await service.retry_generation(session, input_record_id, creator_id)
    return GenerationInitiatedResponse(
        input_record_id=record.input_record_id,
        generation_request_id=record.generation_request_id,
        workflow_state=record.workflow_state,
    )


@router.post(
    "/{input_record_id}/duplicate",
    response_model=InputRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_input(
    input_record_id: uuid.UUID,
    creator_id: Annotated[uuid.UUID, Depends(get_current_creator_id)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    service: Annotated[ScriptPromptIngestionService, Depends(get_service)],
) -> InputRecordResponse:
    """Duplicate an existing record as a new Draft."""
    record = await service.duplicate_input_record(
        session, input_record_id, creator_id
    )
    return InputRecordResponse.model_validate(record)
