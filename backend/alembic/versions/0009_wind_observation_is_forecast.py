"""Add ``wind_observations.is_forecast`` — distinguishes provisional
Open-Meteo forecast readings from reconciled archive/reanalysis values, so a
periodic job can later overwrite the former with the latter once available
(see ``services/wind_lookup.reconcile_forecasts``). Existing rows default to
``false`` (unknown provenance, treated as already-settled) since only new
forecast-endpoint fetches from this point on are marked ``true``.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'wind_observations',
        sa.Column('is_forecast', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('wind_observations', 'is_forecast')
