"""Create script_prompt_inputs table.

Revision ID: 001
Revises: None
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

input_type_enum = sa.Enum(
    "written_script",
    "topic_outline",
    "structured_prompt",
    name="input_type_enum",
)

workflow_state_enum = sa.Enum(
    "draft",
    "submitted",
    "validation_failed",
    "generation_initiated",
    name="workflow_state_enum",
)


def upgrade() -> None:
    input_type_enum.create(op.get_bind(), checkfirst=True)
    workflow_state_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "script_prompt_inputs",
        sa.Column("input_record_id", sa.Uuid(), primary_key=True),
        sa.Column("creator_id", sa.Uuid(), nullable=False),
        sa.Column("input_type", input_type_enum, nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column(
            "workflow_state",
            workflow_state_enum,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("generation_request_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_modified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index(
        "ix_script_prompt_inputs_creator_id",
        "script_prompt_inputs",
        ["creator_id"],
    )
    op.create_index(
        "ix_script_prompt_inputs_workflow_state",
        "script_prompt_inputs",
        ["workflow_state"],
    )
    op.create_index(
        "ix_script_prompt_inputs_creator_state",
        "script_prompt_inputs",
        ["creator_id", "workflow_state"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_script_prompt_inputs_creator_state",
        table_name="script_prompt_inputs",
    )
    op.drop_index(
        "ix_script_prompt_inputs_workflow_state",
        table_name="script_prompt_inputs",
    )
    op.drop_index(
        "ix_script_prompt_inputs_creator_id",
        table_name="script_prompt_inputs",
    )
    op.drop_table("script_prompt_inputs")
    workflow_state_enum.drop(op.get_bind(), checkfirst=True)
    input_type_enum.drop(op.get_bind(), checkfirst=True)
