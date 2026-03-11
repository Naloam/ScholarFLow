"""merge_heads

Revision ID: 7ad38dfe2acf
Revises: 554a1d9ff056, 9f3a2c7d4c1b
Create Date: 2026-03-11 20:50:56.823325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7ad38dfe2acf'
down_revision: Union[str, None] = ('554a1d9ff056', '9f3a2c7d4c1b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
