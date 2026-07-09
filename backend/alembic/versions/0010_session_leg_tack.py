"""Add ``session_legs.tack`` (port/starboard) — the sign of the true wind
angle was discarded before this (``avg_twa_deg`` is stored unsigned), so
there was no way to tell which side of the boat the wind was on for a leg.
Needed for the port/starboard tack comparison in the session analysis UI
(see ``workers/process_upload/processing/straight_lines.py::segment_legs``).

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('session_legs', sa.Column('tack', sa.String(), nullable=True))
    op.create_check_constraint(
        'tack_allowed', 'session_legs', "tack IN ('port', 'starboard')",
    )


def downgrade() -> None:
    op.drop_constraint('tack_allowed', 'session_legs', type_='check')
    op.drop_column('session_legs', 'tack')
