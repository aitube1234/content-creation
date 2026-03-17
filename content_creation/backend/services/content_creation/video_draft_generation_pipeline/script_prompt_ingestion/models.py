"""SQLAlchemy ORM models for script prompt ingestion."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Index, Integer, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class InputType(str, enum.Enum):
    """Types of content input for video generation."""

    WRITTEN_SCRIPT = "written_script"
    TOPIC_OUTLINE = "topic_outline"
    STRUCTURED_PROMPT = "structured_prompt"


class WorkflowState(str, enum.Enum):
    """Lifecycle states for a script prompt input record."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    VALIDATION_FAILED = "validation_failed"
    GENERATION_INITIATED = "generation_initiated"


class ScriptPromptInput(Base):
    """Persisted script/prompt input record for video generation."""

    __tablename__ = "script_prompt_inputs"

    input_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    input_type: Mapped[InputType | None] = mapped_column(
        Enum(InputType, name="input_type_enum", create_type=True),
        nullable=True,
    )
    content_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    workflow_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState, name="workflow_state_enum", create_type=True),
        nullable=False,
        default=WorkflowState.DRAFT,
        index=True,
    )
    validation_errors: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    generation_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    __table_args__ = (
        Index("ix_script_prompt_inputs_creator_state", "creator_id", "workflow_state"),
    )
