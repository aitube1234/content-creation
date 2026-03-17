"""SQLAlchemy ORM models for AI video draft assembly."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Index, Integer, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    Base,
)


class ContentInputType(str, enum.Enum):
    """Types of creator input for video draft assembly."""

    SCRIPT = "script"
    TOPIC_PROMPT = "topic_prompt"


class LifecycleState(str, enum.Enum):
    """Content lifecycle states managed by the Content Lifecycle Management state machine."""

    DRAFT = "draft"
    PRE_PUBLISH = "pre_publish"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AssemblyStatus(str, enum.Enum):
    """Status of the AI assembly pipeline execution."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MetadataStatus(str, enum.Enum):
    """Status of AI metadata generation and attachment."""

    GENERATED = "generated"
    PENDING = "pending"
    MANUALLY_ENTERED = "manually_entered"


class ContentItem(Base):
    """Persisted content item record for AI video draft assembly."""

    __tablename__ = "content_items"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    input_type: Mapped[ContentInputType] = mapped_column(
        Enum(ContentInputType, name="content_input_type_enum", create_type=True),
        nullable=False,
    )
    input_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    input_locale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    lifecycle_state: Mapped[LifecycleState] = mapped_column(
        Enum(LifecycleState, name="lifecycle_state_enum", create_type=True),
        nullable=False,
        default=LifecycleState.DRAFT,
        index=True,
    )
    assembly_status: Mapped[AssemblyStatus] = mapped_column(
        Enum(AssemblyStatus, name="assembly_status_enum", create_type=True),
        nullable=False,
        default=AssemblyStatus.PENDING,
        index=True,
    )
    video_draft_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    scenes: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    metadata_status: Mapped[MetadataStatus | None] = mapped_column(
        Enum(MetadataStatus, name="metadata_status_enum", create_type=True),
        nullable=True,
    )
    ai_title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_tags: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    ai_topic_cluster: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    thumbnail_options: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    selected_thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    version_history: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_content_items_creator_lifecycle", "creator_id", "lifecycle_state"),
        Index("ix_content_items_creator_assembly", "creator_id", "assembly_status"),
    )
