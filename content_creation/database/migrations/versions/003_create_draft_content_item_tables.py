"""Create draft content item tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

creation_source_enum = sa.Enum(
    "script_to_video",
    "co_creator_workspace",
    name="creation_source_enum",
)

metadata_engine_write_status_enum = sa.Enum(
    "confirmed",
    "pending",
    "failed",
    name="metadata_engine_write_status_enum",
)

version_event_type_enum = sa.Enum(
    "draft_created",
    "scene_edit",
    "metadata_override",
    "thumbnail_change",
    "contributor_input",
    "harmonisation_output",
    name="version_event_type_enum",
)

actor_role_enum = sa.Enum(
    "lead_creator",
    "contributor",
    name="actor_role_enum",
)

contribution_status_enum = sa.Enum(
    "pending",
    "accepted",
    "overridden",
    name="contribution_status_enum",
)

report_status_enum = sa.Enum(
    "completed",
    "timeout",
    "failed",
    name="report_status_enum",
)

# Reuse existing enums from migration 002
lifecycle_state_enum = sa.Enum(
    "draft",
    "pre_publish",
    "published",
    "archived",
    name="lifecycle_state_enum",
)

metadata_status_enum = sa.Enum(
    "generated",
    "pending",
    "manually_entered",
    name="metadata_status_enum",
)


def upgrade() -> None:
    # Create new enum types
    creation_source_enum.create(op.get_bind(), checkfirst=True)
    metadata_engine_write_status_enum.create(op.get_bind(), checkfirst=True)
    version_event_type_enum.create(op.get_bind(), checkfirst=True)
    actor_role_enum.create(op.get_bind(), checkfirst=True)
    contribution_status_enum.create(op.get_bind(), checkfirst=True)
    report_status_enum.create(op.get_bind(), checkfirst=True)

    # --- draft_content_items table ---
    op.create_table(
        "draft_content_items",
        sa.Column("content_item_id", sa.Uuid(), primary_key=True),
        sa.Column("lead_creator_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "lifecycle_state",
            lifecycle_state_enum,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("creation_source", creation_source_enum, nullable=False),
        sa.Column("video_draft_url", sa.Text(), nullable=True),
        sa.Column(
            "metadata_status",
            metadata_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("selected_thumbnail_id", sa.Uuid(), nullable=True),
        sa.Column("originality_report_id", sa.Uuid(), nullable=True),
        sa.Column("pipeline_job_reference", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_draft_content_items_lead_creator",
        "draft_content_items",
        ["lead_creator_account_id"],
    )
    op.create_index(
        "ix_draft_content_items_lifecycle_state",
        "draft_content_items",
        ["lifecycle_state"],
    )
    op.create_index(
        "ix_draft_content_items_creator_lifecycle",
        "draft_content_items",
        ["lead_creator_account_id", "lifecycle_state"],
    )
    op.create_index(
        "ix_draft_content_items_creator_source",
        "draft_content_items",
        ["lead_creator_account_id", "creation_source"],
    )

    # --- ai_generated_metadata table ---
    op.create_table(
        "ai_generated_metadata",
        sa.Column("metadata_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_item_id",
            sa.Uuid(),
            sa.ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ai_title_suggestion", sa.Text(), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("ai_topic_tags", sa.JSON(), nullable=True),
        sa.Column("ai_topic_cluster", sa.Text(), nullable=True),
        sa.Column("creator_override_title", sa.Text(), nullable=True),
        sa.Column("creator_override_description", sa.Text(), nullable=True),
        sa.Column("creator_override_tags", sa.JSON(), nullable=True),
        sa.Column(
            "metadata_engine_write_status",
            metadata_engine_write_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_ai_generated_metadata_content_item",
        "ai_generated_metadata",
        ["content_item_id"],
    )

    # --- ai_generated_thumbnails table ---
    op.create_table(
        "ai_generated_thumbnails",
        sa.Column("thumbnail_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_item_id",
            sa.Uuid(),
            sa.ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thumbnail_url", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_ai_generated_thumbnails_content_item",
        "ai_generated_thumbnails",
        ["content_item_id"],
    )

    # --- version_history_entries table ---
    op.create_table(
        "version_history_entries",
        sa.Column("version_entry_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_item_id",
            sa.Uuid(),
            sa.ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", version_event_type_enum, nullable=False),
        sa.Column("actor_account_id", sa.Uuid(), nullable=False),
        sa.Column("actor_role", actor_role_enum, nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=True),
        sa.Column("contribution_status", contribution_status_enum, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_version_history_entries_content_item",
        "version_history_entries",
        ["content_item_id"],
    )
    op.create_index(
        "ix_version_history_content_actor",
        "version_history_entries",
        ["content_item_id", "actor_account_id"],
    )

    # --- originality_reports table ---
    op.create_table(
        "originality_reports",
        sa.Column("originality_report_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "content_item_id",
            sa.Uuid(),
            sa.ForeignKey("draft_content_items.content_item_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("creator_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "duplicate_risk_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("similar_content_items", sa.JSON(), nullable=True),
        sa.Column("differentiation_recommendations", sa.JSON(), nullable=True),
        sa.Column("report_status", report_status_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_originality_reports_content_item",
        "originality_reports",
        ["content_item_id"],
    )
    op.create_index(
        "ix_originality_reports_creator",
        "originality_reports",
        ["creator_account_id"],
    )
    op.create_index(
        "ix_originality_reports_content_creator",
        "originality_reports",
        ["content_item_id", "creator_account_id"],
    )


def downgrade() -> None:
    # Drop indexes and tables in reverse dependency order
    op.drop_index("ix_originality_reports_content_creator", table_name="originality_reports")
    op.drop_index("ix_originality_reports_creator", table_name="originality_reports")
    op.drop_index("ix_originality_reports_content_item", table_name="originality_reports")
    op.drop_table("originality_reports")

    op.drop_index("ix_version_history_content_actor", table_name="version_history_entries")
    op.drop_index("ix_version_history_entries_content_item", table_name="version_history_entries")
    op.drop_table("version_history_entries")

    op.drop_index("ix_ai_generated_thumbnails_content_item", table_name="ai_generated_thumbnails")
    op.drop_table("ai_generated_thumbnails")

    op.drop_index("ix_ai_generated_metadata_content_item", table_name="ai_generated_metadata")
    op.drop_table("ai_generated_metadata")

    op.drop_index("ix_draft_content_items_creator_source", table_name="draft_content_items")
    op.drop_index("ix_draft_content_items_creator_lifecycle", table_name="draft_content_items")
    op.drop_index("ix_draft_content_items_lifecycle_state", table_name="draft_content_items")
    op.drop_index("ix_draft_content_items_lead_creator", table_name="draft_content_items")
    op.drop_table("draft_content_items")

    report_status_enum.drop(op.get_bind(), checkfirst=True)
    contribution_status_enum.drop(op.get_bind(), checkfirst=True)
    actor_role_enum.drop(op.get_bind(), checkfirst=True)
    version_event_type_enum.drop(op.get_bind(), checkfirst=True)
    metadata_engine_write_status_enum.drop(op.get_bind(), checkfirst=True)
    creation_source_enum.drop(op.get_bind(), checkfirst=True)
