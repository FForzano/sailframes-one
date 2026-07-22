"""Versioned legal acceptance on users: track which version of the Terms of
Service and Privacy Policy each user last accepted, and when.

Replaces the single generic ``terms_and_conditions`` boolean (kept for
backward compatibility) with per-document version + timestamp columns, so the
app can require re-acceptance whenever a document changes (see backend/legal.py
and the capabilities ``legal.needs_acceptance`` flag).

Backfill: existing users who had ``terms_and_conditions = true`` only ever
accepted the old, pre-versioning generic checkbox — with no real document text
behind it. They are stamped with the sentinel ``'legacy'`` version for BOTH
documents, which never equals a current version, so they are prompted to
formally accept the new Terms and Privacy Policy on their next visit. Users
who never accepted (``false``) keep NULL and are likewise prompted.

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0033'
down_revision: Union[str, None] = '0032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('terms_version', sa.String(), nullable=True))
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('privacy_version', sa.String(), nullable=True))
    op.add_column('users', sa.Column('privacy_accepted_at', sa.DateTime(timezone=True), nullable=True))

    # Backfill: mark previously-accepted users as 'legacy' so the new formal
    # documents are presented for (re-)acceptance. Timestamps stay NULL — we
    # don't know when the old checkbox was ticked.
    op.execute(
        "UPDATE users SET terms_version = 'legacy', privacy_version = 'legacy' "
        "WHERE terms_and_conditions = true"
    )


def downgrade() -> None:
    op.drop_column('users', 'privacy_accepted_at')
    op.drop_column('users', 'privacy_version')
    op.drop_column('users', 'terms_accepted_at')
    op.drop_column('users', 'terms_version')
