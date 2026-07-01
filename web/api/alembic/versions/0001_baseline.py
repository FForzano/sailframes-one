"""baseline schema (RBAC scaffold + user-system Phase 1 tables)

Materialises the full current schema from the ORM metadata: the pre-existing
race/regatta/raceday/boat/session tables, the RBAC scaffold, and the Phase 1
user-system tables (club owner/visibility columns, club_members,
auth_refresh_tokens). Later phase migrations are explicit ``op.*`` operations
against this baseline.

Bootstrapping an already-``create_all``'d DB with no data: run
``alembic -c web/api/alembic.ini stamp head`` instead of ``upgrade``.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op

from api.db.base import Base
import api.db.models  # noqa: F401  (registers all tables on Base.metadata)

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
