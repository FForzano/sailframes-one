"""Add ``session_uploads.reanalysis_status``/``reanalysis_error`` — tracks
the background job kicked off by ``POST /sessions/{id}/reanalyze`` and
``POST /sessions/{id}/wind/refresh`` (NULL/"running"/"failed"), separate
from ``status`` which tracks the ingestion pipeline.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('session_uploads', sa.Column('reanalysis_status', sa.String(), nullable=True))
    op.add_column('session_uploads', sa.Column('reanalysis_error', sa.String(), nullable=True))
    op.create_check_constraint(
        'reanalysis_status_allowed', 'session_uploads',
        "reanalysis_status IN ('running', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint('reanalysis_status_allowed', 'session_uploads', type_='check')
    op.drop_column('session_uploads', 'reanalysis_error')
    op.drop_column('session_uploads', 'reanalysis_status')
