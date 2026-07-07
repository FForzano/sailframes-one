"""Add ``activities.thumbnail_image_id`` — an overlay PNG with every
session's track in the activity drawn in a different color.

Rendered by the processing worker (composited from each session's
gps.json) and stored as a normal ``images`` row, so the unified
Activities list can show a preview without recomputing it on every
page load.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'activities',
        sa.Column('thumbnail_image_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'activities_thumbnail_image_id_fkey',
        'activities', 'images',
        ['thumbnail_image_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'activities_thumbnail_image_id_fkey', 'activities', type_='foreignkey',
    )
    op.drop_column('activities', 'thumbnail_image_id')
