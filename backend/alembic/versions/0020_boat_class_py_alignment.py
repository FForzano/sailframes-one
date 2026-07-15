"""Align ``boat_classes`` PY-related fields with the official RYA
Portsmouth Yardstick list structure (RYA Class ID / Rig / Spinnaker /
Number columns) so an admin transcribing the published PDF has a 1:1
field mapping.

- ``py_rating``: was a free ``FLOAT`` — the RYA "Number" column is
  always an integer, so tighten it to ``INTEGER``. Existing values are
  truncated (rounded) on the way in.
- ``rig_type``: was free text — restrict to the RYA "Rig" column's two
  values (``sloop``/``una``, i.e. S/U in the RYA table).
- ``spinnaker_type``: new column mapping the RYA "Spinnaker" column
  (``0``/``A``/``C`` in the table) to ``none``/``asymmetric``/``symmetric``.
- ``rya_class_id``: new nullable, unique column for the official RYA
  Class ID (e.g. 191 for ILCA 7 / Laser) — reference only, no
  import/sync built on top of it yet.

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0020'
down_revision: Union[str, None] = '0019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'boat_classes', 'py_rating',
        type_=sa.Integer(),
        postgresql_using='round(py_rating)::integer',
    )

    op.execute("UPDATE boat_classes SET rig_type = NULL "
               "WHERE rig_type NOT IN ('sloop', 'una')")
    op.create_check_constraint(
        'rig_type_allowed', 'boat_classes',
        "rig_type IN ('sloop', 'una')",
    )

    op.add_column('boat_classes', sa.Column('spinnaker_type', sa.String(), nullable=True))
    op.create_check_constraint(
        'spinnaker_type_allowed', 'boat_classes',
        "spinnaker_type IN ('none', 'asymmetric', 'symmetric')",
    )

    op.add_column('boat_classes', sa.Column('rya_class_id', sa.Integer(), nullable=True))
    op.create_unique_constraint('uq_boat_classes_rya_class_id', 'boat_classes', ['rya_class_id'])


def downgrade() -> None:
    op.drop_constraint('uq_boat_classes_rya_class_id', 'boat_classes', type_='unique')
    op.drop_column('boat_classes', 'rya_class_id')

    op.drop_constraint('spinnaker_type_allowed', 'boat_classes', type_='check')
    op.drop_column('boat_classes', 'spinnaker_type')

    op.drop_constraint('rig_type_allowed', 'boat_classes', type_='check')

    op.alter_column('boat_classes', 'py_rating', type_=sa.Float())
