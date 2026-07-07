"""Add ``session_analysis.thumbnail_image_id`` — a small track-preview PNG.

Rendered once by the processing worker from ``gps.json`` and stored as a
normal ``images`` row, so the sessions list can show a track thumbnail
without re-rendering the track on every page load.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'session_analysis',
        sa.Column('thumbnail_image_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'session_analysis_thumbnail_image_id_fkey',
        'session_analysis', 'images',
        ['thumbnail_image_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'session_analysis_thumbnail_image_id_fkey', 'session_analysis', type_='foreignkey',
    )
    op.drop_column('session_analysis', 'thumbnail_image_id')
