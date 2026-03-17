"""paper_url_column

Revision ID: a1b2c3d4e5f6
Revises: 7c8d9e0f1a2b
Create Date: 2026-03-17 22:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7c8d9e0f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("papers", "url")
