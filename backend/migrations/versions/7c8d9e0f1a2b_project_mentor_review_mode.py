"""project_mentor_review_mode

Revision ID: 7c8d9e0f1a2b
Revises: 59cf0f12ab4d
Create Date: 2026-03-17 20:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c8d9e0f1a2b"
down_revision: Union[str, None] = "59cf0f12ab4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_mentor_access",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("mentor_user_id", sa.String(), nullable=True),
        sa.Column("mentor_email", sa.String(), nullable=False),
        sa.Column("invited_by_user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["mentor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_mentor_access_project_id",
        "project_mentor_access",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_mentor_access_mentor_email",
        "project_mentor_access",
        ["mentor_email"],
        unique=False,
    )
    op.create_index(
        "ux_project_mentor_access_project_email",
        "project_mentor_access",
        ["project_id", "mentor_email"],
        unique=True,
    )

    op.create_table(
        "mentor_feedback",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("mentor_user_id", sa.String(), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=False),
        sa.Column("concerns", sa.Text(), nullable=False),
        sa.Column("next_steps", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mentor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mentor_feedback_project_id", "mentor_feedback", ["project_id"], unique=False)
    op.create_index("ix_mentor_feedback_mentor_user_id", "mentor_feedback", ["mentor_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mentor_feedback_mentor_user_id", table_name="mentor_feedback")
    op.drop_index("ix_mentor_feedback_project_id", table_name="mentor_feedback")
    op.drop_table("mentor_feedback")
    op.drop_index("ux_project_mentor_access_project_email", table_name="project_mentor_access")
    op.drop_index("ix_project_mentor_access_mentor_email", table_name="project_mentor_access")
    op.drop_index("ix_project_mentor_access_project_id", table_name="project_mentor_access")
    op.drop_table("project_mentor_access")
