"""audit_event_metadata

Revision ID: 3c6c4f5b9a2e
Revises: 0f4c6d2a9b11
Create Date: 2026-03-17 14:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c6c4f5b9a2e"
down_revision: Union[str, None] = "0f4c6d2a9b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("event_type", sa.String(), server_default="http", nullable=False),
    )
    op.add_column(
        "audit_logs",
        sa.Column("action", sa.String(), server_default="request", nullable=False),
    )
    op.add_column("audit_logs", sa.Column("resource_id", sa.String(), nullable=True))
    op.add_column("audit_logs", sa.Column("detail", sa.Text(), nullable=True))
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"], unique=False)
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_column("audit_logs", "detail")
    op.drop_column("audit_logs", "resource_id")
    op.drop_column("audit_logs", "action")
    op.drop_column("audit_logs", "event_type")
