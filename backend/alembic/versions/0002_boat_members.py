"""Phase 2 — boat standing crew (boat_members) + boats.club_id

Adds the ``boat_members`` table (standing crew: owner|skipper|crew|viewer) and
a structured ``boats.club_id`` reference (kept alongside the legacy free-text
``boats.club`` in dual-read until the UI migrates).

Uses ``batch_alter_table`` for the ``boats`` changes so the same revision runs
on Postgres (production) and on the SQLite stand-in used for tests (SQLite has
no ``ALTER TABLE ... ADD CONSTRAINT``).

Revision ID: 0002_boat_members
Revises: 0001_baseline
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_boat_members"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "boat_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("boat_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["boat_id"], ["boats.boat_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("boat_id", "user_id", name="uq_boat_member"),
    )
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.add_column(sa.Column("club_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_boats_club_id", "clubs", ["club_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("boats", schema=None) as batch_op:
        batch_op.drop_constraint("fk_boats_club_id", type_="foreignkey")
        batch_op.drop_column("club_id")
    op.drop_table("boat_members")
