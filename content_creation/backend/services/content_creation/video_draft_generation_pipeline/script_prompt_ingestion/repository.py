"""Repository layer for script prompt input database access."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    InputType,
    ScriptPromptInput,
    WorkflowState,
)

logger = logging.getLogger(__name__)


class ScriptPromptInputRepository:
    """Provides all async database access methods for ScriptPromptInput."""

    async def create(
        self,
        session: AsyncSession,
        data: dict[str, Any],
    ) -> ScriptPromptInput:
        """Insert a new input record with state=Draft."""
        record = ScriptPromptInput(
            input_record_id=uuid.uuid4(),
            creator_id=data["creator_id"],
            input_type=data.get("input_type"),
            content_text=data["content_text"],
            workflow_state=WorkflowState.DRAFT,
            character_count=len(data["content_text"]),
            created_at=datetime.now(timezone.utc),
            last_modified_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        logger.debug(
            "Created input record %s for creator %s",
            record.input_record_id,
            record.creator_id,
        )
        return record

    async def get_by_id(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput | None:
        """Fetch a single record scoped to the creator."""
        stmt = select(ScriptPromptInput).where(
            ScriptPromptInput.input_record_id == input_record_id,
            ScriptPromptInput.creator_id == creator_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
        data: dict[str, Any],
    ) -> ScriptPromptInput | None:
        """Update mutable fields on a record; always update last_modified_at."""
        update_data: dict[str, Any] = {
            **data,
            "last_modified_at": datetime.now(timezone.utc),
        }
        if "content_text" in data and data["content_text"] is not None:
            update_data["character_count"] = len(data["content_text"])

        stmt = (
            update(ScriptPromptInput)
            .where(
                ScriptPromptInput.input_record_id == input_record_id,
                ScriptPromptInput.creator_id == creator_id,
            )
            .values(**update_data)
            .returning(ScriptPromptInput)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
            logger.debug("Updated input record %s", input_record_id)
        return record

    async def delete(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> bool:
        """Delete only if workflow_state=Draft. Returns False if not deletable."""
        stmt = (
            delete(ScriptPromptInput)
            .where(
                ScriptPromptInput.input_record_id == input_record_id,
                ScriptPromptInput.creator_id == creator_id,
                ScriptPromptInput.workflow_state == WorkflowState.DRAFT,
            )
        )
        result = await session.execute(stmt)
        await session.flush()
        deleted = result.rowcount > 0
        if deleted:
            logger.debug("Deleted input record %s", input_record_id)
        return deleted

    async def update_workflow_state(
        self,
        session: AsyncSession,
        input_record_id: uuid.UUID,
        new_state: WorkflowState,
        extra_fields: dict[str, Any] | None = None,
    ) -> ScriptPromptInput | None:
        """Atomic state transition with optional extra field updates."""
        update_data: dict[str, Any] = {
            "workflow_state": new_state,
            "last_modified_at": datetime.now(timezone.utc),
        }
        if extra_fields:
            update_data.update(extra_fields)

        stmt = (
            update(ScriptPromptInput)
            .where(ScriptPromptInput.input_record_id == input_record_id)
            .values(**update_data)
            .returning(ScriptPromptInput)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            await session.flush()
            logger.debug(
                "Updated workflow state for %s to %s",
                input_record_id,
                new_state.value,
            )
        return record

    async def list_by_creator(
        self,
        session: AsyncSession,
        creator_id: uuid.UUID,
        input_type: InputType | None = None,
        workflow_state: WorkflowState | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ScriptPromptInput], int]:
        """Paginated, filterable, sortable history list."""
        base_filter = ScriptPromptInput.creator_id == creator_id

        count_stmt = select(func.count()).select_from(ScriptPromptInput).where(base_filter)
        query_stmt = select(ScriptPromptInput).where(base_filter)

        if input_type is not None:
            count_stmt = count_stmt.where(ScriptPromptInput.input_type == input_type)
            query_stmt = query_stmt.where(ScriptPromptInput.input_type == input_type)
        if workflow_state is not None:
            count_stmt = count_stmt.where(ScriptPromptInput.workflow_state == workflow_state)
            query_stmt = query_stmt.where(ScriptPromptInput.workflow_state == workflow_state)

        sort_column = getattr(ScriptPromptInput, sort_by, ScriptPromptInput.created_at)
        if sort_order == "asc":
            query_stmt = query_stmt.order_by(sort_column.asc())
        else:
            query_stmt = query_stmt.order_by(sort_column.desc())

        query_stmt = query_stmt.offset(offset).limit(limit)

        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        records_result = await session.execute(query_stmt)
        records = list(records_result.scalars().all())

        return records, total

    async def duplicate(
        self,
        session: AsyncSession,
        source_record_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> ScriptPromptInput | None:
        """Create a new Draft copy with identical content and type."""
        source = await self.get_by_id(session, source_record_id, creator_id)
        if source is None:
            return None

        new_record = ScriptPromptInput(
            input_record_id=uuid.uuid4(),
            creator_id=creator_id,
            input_type=source.input_type,
            content_text=source.content_text,
            workflow_state=WorkflowState.DRAFT,
            character_count=source.character_count,
            created_at=datetime.now(timezone.utc),
            last_modified_at=datetime.now(timezone.utc),
        )
        session.add(new_record)
        await session.flush()
        logger.debug(
            "Duplicated record %s as %s",
            source_record_id,
            new_record.input_record_id,
        )
        return new_record
