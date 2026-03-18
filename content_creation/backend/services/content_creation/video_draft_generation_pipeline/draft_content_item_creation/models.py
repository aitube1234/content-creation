"""SQLAlchemy ORM models for draft content item creation."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.services.content_creation.video_draft_generation_pipeline.script_prompt_ingestion.models import (
    Base,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.models import (
    LifecycleState,
    MetadataStatus,
)
from backend.services.content_creation.video_draft_generation_pipeline.draft_content_item_creation.enums import (
    ActorRole,
    ContributionStatus,
    CreationSource,
    MetadataEngineWriteStatus,
    ReportStatus,
    VersionEventType,
)


class DraftContentItem(Base):
    """Persisted draft content item record."""

    __tablename__ = "draft_content_items"

    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    lead_creator_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    lifecycle_state: Mapped[LifecycleState] = mapped_column(
        Enum(LifecycleState, name="lifecycle_state_enum", create_type=False),
        nullable=False,
        default=LifecycleState.DRAFT,
        index=True,
    )
    creation_source: Mapped[CreationSource] = mapped_column(
        Enum(CreationSource, name="creation_source_enum", create_type=True),
        nullable=False,
    )
    video_draft_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    metadata_status: Mapped[MetadataStatus] = mapped_column(
        Enum(MetadataStatus, name="metadata_status_enum", create_type=False),
        nullable=False,
        default=MetadataStatus.PENDING,
    )
    selected_thumbnail_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )
    originality_report_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        nullable=True,
    )
    pipeline_job_reference: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    # Relationships
    ai_metadata: Mapped["AIGeneratedMetadata | None"] = relationship(
        back_populates="draft_content_item",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    thumbnails: Mapped[list["AIGeneratedThumbnail"]] = relationship(
        back_populates="draft_content_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    version_history_entries: Mapped[list["VersionHistoryEntry"]] = relationship(
        back_populates="draft_content_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    originality_reports: Mapped[list["OriginalityReport"]] = relationship(
        back_populates="draft_content_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_draft_content_items_creator_lifecycle",
            "lead_creator_account_id",
            "lifecycle_state",
        ),
        Index(
            "ix_draft_content_items_creator_source",
            "lead_creator_account_id",
            "creation_source",
        ),
    )


class AIGeneratedMetadata(Base):
    """AI-generated metadata attached to a draft content item."""

    __tablename__ = "ai_generated_metadata"

    metadata_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ai_title_suggestion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_topic_tags: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    ai_topic_cluster: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    creator_override_title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    creator_override_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    creator_override_tags: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    metadata_engine_write_status: Mapped[MetadataEngineWriteStatus] = mapped_column(
        Enum(
            MetadataEngineWriteStatus,
            name="metadata_engine_write_status_enum",
            create_type=True,
        ),
        nullable=False,
        default=MetadataEngineWriteStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    draft_content_item: Mapped["DraftContentItem"] = relationship(
        back_populates="ai_metadata",
    )


class AIGeneratedThumbnail(Base):
    """AI-generated thumbnail option for a draft content item."""

    __tablename__ = "ai_generated_thumbnails"

    thumbnail_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thumbnail_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    is_selected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    draft_content_item: Mapped["DraftContentItem"] = relationship(
        back_populates="thumbnails",
    )


class VersionHistoryEntry(Base):
    """Version history entry tracking changes to a draft content item."""

    __tablename__ = "version_history_entries"

    version_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[VersionEventType] = mapped_column(
        Enum(VersionEventType, name="version_event_type_enum", create_type=True),
        nullable=False,
    )
    actor_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
    )
    actor_role: Mapped[ActorRole] = mapped_column(
        Enum(ActorRole, name="actor_role_enum", create_type=True),
        nullable=False,
    )
    event_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    contribution_status: Mapped[ContributionStatus | None] = mapped_column(
        Enum(ContributionStatus, name="contribution_status_enum", create_type=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    draft_content_item: Mapped["DraftContentItem"] = relationship(
        back_populates="version_history_entries",
    )

    __table_args__ = (
        Index(
            "ix_version_history_content_actor",
            "content_item_id",
            "actor_account_id",
        ),
    )


class OriginalityReport(Base):
    """Originality check report for a draft content item."""

    __tablename__ = "originality_reports"

    originality_report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    creator_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True,
    )
    duplicate_risk_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    similar_content_items: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    differentiation_recommendations: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    report_status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum", create_type=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    draft_content_item: Mapped["DraftContentItem"] = relationship(
        back_populates="originality_reports",
    )

    __table_args__ = (
        Index(
            "ix_originality_reports_content_creator",
            "content_item_id",
            "creator_account_id",
        ),
    )
