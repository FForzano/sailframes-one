"""baseline schema (RBAC scaffold + user-system Phase 1 tables)

Point-in-time CREATE of the full schema as of **Phase 1** (end of the native
login / clubs commit): the pre-existing race/regatta/raceday/boat/session
tables, the RBAC scaffold, and the Phase 1 user-system tables (club
owner/visibility columns, ``club_members``, ``auth_refresh_tokens``).

⚠️ **Frozen** — this revision is deliberately written as explicit ``op.*``
operations rather than ``Base.metadata.create_all`` so it stays pinned to the
Phase-1 schema. Later phases (2+) add their own explicit revisions on top; if
this were still ``create_all`` off the live metadata, a fresh DB would get
every later phase's columns/tables from ``0001`` and the ``0001 -> 0002`` chain
would break. Do NOT reintroduce ``create_all`` here.

Bootstrapping an already-``create_all``'d DB with no data: run
``alembic -c web/api/alembic.ini stamp head`` instead of ``upgrade``.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "boats",
        sa.Column("boat_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("sail_number", sa.String(), nullable=False),
        sa.Column("club", sa.String(), nullable=False),
        sa.Column("loa_m", sa.Float(), nullable=True),
        sa.Column("skippers", sa.JSON(), nullable=False),
        sa.Column("photos", sa.JSON(), nullable=False),
        sa.Column("cert_url", sa.String(), nullable=True),
        sa.Column("mbsa_url", sa.String(), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("polar", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("boat_id"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "race_days",
        sa.Column("raceday_id", sa.String(), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("regatta_id", sa.String(), nullable=True),
        sa.Column("race_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("raceday_id"),
    )
    op.create_table(
        "races",
        sa.Column("race_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("start_time", sa.String(), nullable=False),
        sa.Column("end_time", sa.String(), nullable=False),
        sa.Column("regatta_id", sa.String(), nullable=True),
        sa.Column("raceday_id", sa.String(), nullable=True),
        sa.Column("start_line", sa.JSON(), nullable=True),
        sa.Column("finish_line", sa.JSON(), nullable=True),
        sa.Column("course", sa.JSON(), nullable=False),
        sa.Column("finish_order", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("race_id"),
    )
    op.create_table(
        "regattas",
        sa.Column("regatta_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("venue", sa.String(), nullable=False),
        sa.Column("boat_class", sa.JSON(), nullable=True),
        sa.Column("start_date", sa.String(), nullable=True),
        sa.Column("end_date", sa.String(), nullable=True),
        sa.Column("rating_system", sa.String(), nullable=True),
        sa.Column("start_sequence_minutes", sa.Integer(), nullable=True),
        sa.Column("race_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("regatta_id"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("start_time", sa.String(), nullable=True),
        sa.Column("end_time", sa.String(), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("boat", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("sensors", sa.JSON(), nullable=True),
        sa.Column("has_video", sa.Boolean(), nullable=False),
        sa.Column("has_analysis", sa.Boolean(), nullable=False),
        sa.Column("trim", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "date", name="uq_session_device_date"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("prev_id", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.String(), nullable=True),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_refresh_tokens_family_id"),
        "auth_refresh_tokens", ["family_id"], unique=False,
    )
    op.create_index(
        op.f("ix_auth_refresh_tokens_token_hash"),
        "auth_refresh_tokens", ["token_hash"], unique=True,
    )
    op.create_index(
        op.f("ix_auth_refresh_tokens_user_id"),
        "auth_refresh_tokens", ["user_id"], unique=False,
    )
    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("default_session_visibility", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "marks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("race_id", sa.String(), nullable=False),
        sa.Column("mark_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mark_type", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["race_id"], ["races.race_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "race_boats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("race_id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("boat_id", sa.String(), nullable=True),
        sa.Column("boat_name", sa.String(), nullable=False),
        sa.Column("sail_number", sa.String(), nullable=False),
        sa.Column("session_path", sa.String(), nullable=True),
        sa.Column("gpx_path", sa.String(), nullable=True),
        sa.Column("polar", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["race_id"], ["races.race_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "race_results",
        sa.Column("race_id", sa.String(), nullable=False),
        sa.Column("finish_order", sa.JSON(), nullable=False),
        sa.Column("boat_results", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["race_id"], ["races.race_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("race_id"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_table(
        "club_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("joined_at", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id", "user_id", name="uq_club_member"),
    )
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("scope_club_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("club_members")
    op.drop_table("role_permissions")
    op.drop_table("race_results")
    op.drop_table("race_boats")
    op.drop_table("marks")
    op.drop_table("clubs")
    op.drop_index(op.f("ix_auth_refresh_tokens_user_id"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_token_hash"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_family_id"), table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("sessions")
    op.drop_table("roles")
    op.drop_table("regattas")
    op.drop_table("races")
    op.drop_table("race_days")
    op.drop_table("permissions")
    op.drop_table("boats")
