"""Add app_config singleton table.

Superadmin-editable settings that need to change without a redeploy —
currently just ``min_native_version_android``/``min_native_version_ios``
(separate per platform since Android/iOS release cadences are independent),
used to block outdated native app installs with an "update required" screen
(see docs/native-apps.md, "Forcing a native update"). The single row is
seeded by ``auth.seed.seed_app_config`` on startup, not by this migration.

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0024'
down_revision: Union[str, None] = '0023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_config',
        sa.Column('id', sa.Uuid(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('min_native_version_android', sa.String(), nullable=True),
        sa.Column('min_native_version_ios', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_app_config')),
    )


def downgrade() -> None:
    op.drop_table('app_config')
