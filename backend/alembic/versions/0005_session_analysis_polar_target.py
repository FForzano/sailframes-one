"""Add ``polar_target`` (max-speed-per-bucket polar) to ``session_analysis``.

The worker already supported generating a "target" polar (max speed per
TWA/TWS bucket, vs. the average/actual polar in ``polar_points``) but nothing
persisted it. It's another derived series, not a relational datum, so it
joins the other JSON columns on ``session_analysis`` rather than getting its
own table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('session_analysis', sa.Column('polar_target', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('session_analysis', 'polar_target')
