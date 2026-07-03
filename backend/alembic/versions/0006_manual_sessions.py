"""Manual sessions — device_id/date become optional, add source + processing status

Sessions used to require a device (device_id + date was the whole identity).
A user can now create a session by hand (boat + crew, no device) and attach an
externally-captured GPX track for analysis. ``device_id``/``date`` become
nullable; the existing ``id`` surrogate PK (already present, just DB-side)
becomes the real lookup key for these "manual" sessions since they have no
device/date pair. The old ``uq_session_device_date`` unique constraint is
replaced with a partial unique index so it only applies when both columns are
set (device-sourced sessions keep their old dedup guarantee).

``source`` distinguishes the two kinds; ``processing_status``/``processing_error``
track the async GPX-parse-and-analyze job (device-sourced sessions are already
processed by the CSV ingest pipeline by the time they're visible, so they
default to ``ready``).

Revision ID: 0006_manual_sessions
Revises: 0005_session_privacy
Create Date: 2026-07-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_manual_sessions"
down_revision: Union[str, None] = "0005_session_privacy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column("device_id", existing_type=sa.String(), nullable=True)
        batch_op.alter_column("date", existing_type=sa.String(), nullable=True)
        batch_op.add_column(
            sa.Column("source", sa.String(), nullable=False, server_default="device")
        )
        batch_op.add_column(
            sa.Column("processing_status", sa.String(), nullable=False, server_default="ready")
        )
        batch_op.add_column(sa.Column("processing_error", sa.Text(), nullable=True))
        batch_op.drop_constraint("uq_session_device_date", type_="unique")

    op.create_index(
        "uq_session_device_date_partial",
        "sessions",
        ["device_id", "date"],
        unique=True,
        postgresql_where=sa.text("device_id IS NOT NULL AND date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_session_device_date_partial", table_name="sessions")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_session_device_date", ["device_id", "date"]
        )
        batch_op.drop_column("processing_error")
        batch_op.drop_column("processing_status")
        batch_op.drop_column("source")
        batch_op.alter_column("date", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("device_id", existing_type=sa.String(), nullable=False)
