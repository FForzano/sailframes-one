"""Add reversible trim bounds to sessions.

``trim_start_time``/``trim_end_time`` (unix-epoch seconds, same convention as
``session_maneuvers.start_time``) let a user discard the leading/trailing
portion of a session's track from analysis without touching the raw
``gps.json`` — null means "no trim", the full track is analyzed. Reanalysis
reads these bounds and slices the track before running the pipeline (see
``workers/process_upload/analyzer.py::_slice_by_time``).

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('trim_start_time', sa.Float(), nullable=True))
    op.add_column('sessions', sa.Column('trim_end_time', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'trim_end_time')
    op.drop_column('sessions', 'trim_start_time')
