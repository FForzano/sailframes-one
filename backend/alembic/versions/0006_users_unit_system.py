"""Persist the user's unit-system preference (nautical/metric) on the profile.

Previously stored client-side only (localStorage), which didn't follow the
user across devices/browsers. Existing rows default to 'nautical' (the
current client-side default).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('unit_system', sa.String(), nullable=False, server_default='nautical'),
    )
    op.create_check_constraint(
        'unit_system_allowed', 'users',
        "unit_system IN ('nautical', 'metric')",
    )


def downgrade() -> None:
    op.drop_constraint('unit_system_allowed', 'users', type_='check')
    op.drop_column('users', 'unit_system')
