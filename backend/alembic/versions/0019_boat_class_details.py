"""Add class-specific detail columns to ``boat_classes``.

Lets the admin catalog carry the technical specs of a sailing class
instead of just a name/description/logo — the fields an admin needs to
describe a class (LOA, beam, sail area, crew size, hull type, rig type,
Portsmouth Yardstick / handicap rating) so the "Classi barca" admin page
can expose an edit form for them.

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0019'
down_revision: Union[str, None] = '0018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('boat_classes', sa.Column('loa_m', sa.Float(), nullable=True))
    op.add_column('boat_classes', sa.Column('beam_m', sa.Float(), nullable=True))
    op.add_column('boat_classes', sa.Column('sail_area_sqm', sa.Float(), nullable=True))
    op.add_column('boat_classes', sa.Column('crew_size', sa.Integer(), nullable=True))
    op.add_column('boat_classes', sa.Column('hull_type', sa.String(), nullable=True))
    op.create_check_constraint(
        'hull_type_allowed', 'boat_classes',
        "hull_type IN ('monohull', 'multihull')",
    )
    op.add_column('boat_classes', sa.Column('rig_type', sa.String(), nullable=True))
    op.add_column('boat_classes', sa.Column('py_rating', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('boat_classes', 'py_rating')
    op.drop_column('boat_classes', 'rig_type')
    op.drop_constraint('hull_type_allowed', 'boat_classes', type_='check')
    op.drop_column('boat_classes', 'hull_type')
    op.drop_column('boat_classes', 'crew_size')
    op.drop_column('boat_classes', 'sail_area_sqm')
    op.drop_column('boat_classes', 'beam_m')
    op.drop_column('boat_classes', 'loa_m')
