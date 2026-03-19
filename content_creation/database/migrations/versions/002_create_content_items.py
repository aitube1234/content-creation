"""Create content_items table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

content_input_type_enum = sa.Enum(
    "script",
    "topic_prompt",
    name="content_input_type_enum",
)

lifecycle_state_enum = sa.Enum(
    "draft",
    "pre_publish",
    "published",
    "archived",
    name="lifecycle_state_enum",
)

assembly_status_enum = sa.Enum(
    "pending",
    "processing",
    "completed",
    "failed",
    name="assembly_status_enum",
)

metadata_status_enum = sa.Enum(
    "generated",
    "pending",
    "manually_entered",
    name="metadata_status_enum",
)


def upgrade() -> None:
    content_input_type_enum.create(op.get_bind(), checkfirst=True)
    lifecycle_state_enum.create(op.get_bind(), checkfirst=True)
    assembly_status_enum.create(op.get_bind(), checkfirst=True)
    metadata_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "content_items",
        sa.Column("content_item_id", sa.Uuid(), primary_key=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("input_type", content_input_type_enum, nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("input_locale", sa.Text(), nullable=True),
        sa.Column(
            "lifecycle_state",
            lifecycle_state_enum,
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "assembly_status",
            assembly_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("video_draft_url", sa.Text(), nullable=True),
        sa.Column("scenes", sa.JSON(), nullable=True),
        sa.Column("metadata_status", metadata_status_enum, nullable=True),
        sa.Column("ai_title", sa.Text(), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("ai_tags", sa.JSON(), nullable=True),
        sa.Column("ai_topic_cluster", sa.Text(), nullable=True),
        sa.Column("thumbnail_options", sa.JSON(), nullable=True),
        sa.Column("selected_thumbnail_url", sa.Text(), nullable=True),
        sa.Column("version_history", sa.JSON(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
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
        "ix_content_items_creator_id",
        "content_items",
        ["creator_id"],
    )
    op.create_index(
        "ix_content_items_lifecycle_state",
        "content_items",
        ["lifecycle_state"],
    )
    op.create_index(
        "ix_content_items_assembly_status",
        "content_items",
        ["assembly_status"],
    )
    op.create_index(
        "ix_content_items_creator_lifecycle",
        "content_items",
        ["creator_id", "lifecycle_state"],
    )
    op.create_index(
        "ix_content_items_creator_assembly",
        "content_items",
        ["creator_id", "assembly_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_items_creator_assembly", table_name="content_items")
    op.drop_index("ix_content_items_creator_lifecycle", table_name="content_items")
    op.drop_index("ix_content_items_assembly_status", table_name="content_items")
    op.drop_index("ix_content_items_lifecycle_state", table_name="content_items")
    op.drop_index("ix_content_items_creator_id", table_name="content_items")
    op.drop_table("content_items")
    metadata_status_enum.drop(op.get_bind(), checkfirst=True)
    assembly_status_enum.drop(op.get_bind(), checkfirst=True)
    lifecycle_state_enum.drop(op.get_bind(), checkfirst=True)
    content_input_type_enum.drop(op.get_bind(), checkfirst=True)
