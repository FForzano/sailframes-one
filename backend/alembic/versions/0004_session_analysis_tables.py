"""Persist session analysis: maneuvers, legs, and the JSON leftovers.

The rich analysis produced by the processing worker used to live only as an
``analysis.json`` blob in object storage. This normalizes it into the DB
following the existing pattern: discrete events (tacks/gybes, straight-line
legs) become queryable typed rows, while the non-relational parts (correlation
matrix, per-maneuver distributions, VMG/true-wind series) go in a 1:1 JSON
table. Scalars already have ``session_stats``; the polar curve ``polar_points``.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'session_maneuvers',
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('maneuver_type', sa.String(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('duration_sec', sa.Float(), nullable=False),
        sa.Column('speed_loss_kts', sa.Float(), nullable=False),
        sa.Column('speed_before_kts', sa.Float(), nullable=False),
        sa.Column('speed_min_kts', sa.Float(), nullable=False),
        sa.Column('speed_after_kts', sa.Float(), nullable=False),
        sa.Column('recovery_time_sec', sa.Float(), nullable=False),
        sa.Column('heading_change_deg', sa.Float(), nullable=False),
        sa.Column('max_heel_deg', sa.Float(), nullable=True),
        sa.Column('distance_lost_m', sa.Float(), nullable=True),
        sa.Column('start_lat', sa.Float(), nullable=True),
        sa.Column('start_lon', sa.Float(), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.CheckConstraint("maneuver_type IN ('tack', 'gybe')",
                           name=op.f('ck_session_maneuvers_maneuver_type_allowed')),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'],
                                name=op.f('fk_session_maneuvers_session_id_sessions'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_session_maneuvers')),
    )
    op.create_index(op.f('ix_session_maneuvers_session_id'), 'session_maneuvers',
                    ['session_id'], unique=False)

    op.create_table(
        'session_legs',
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('leg_type', sa.String(), nullable=False),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=False),
        sa.Column('duration_sec', sa.Float(), nullable=False),
        sa.Column('distance_nm', sa.Float(), nullable=False),
        sa.Column('avg_speed_kts', sa.Float(), nullable=False),
        sa.Column('max_speed_kts', sa.Float(), nullable=False),
        sa.Column('avg_vmg_kts', sa.Float(), nullable=False),
        sa.Column('avg_heel_deg', sa.Float(), nullable=True),
        sa.Column('avg_twa_deg', sa.Float(), nullable=True),
        sa.Column('std_heading_deg', sa.Float(), nullable=False),
        sa.Column('num_points', sa.Integer(), nullable=False),
        sa.Column('start_lat', sa.Float(), nullable=True),
        sa.Column('start_lon', sa.Float(), nullable=True),
        sa.Column('end_lat', sa.Float(), nullable=True),
        sa.Column('end_lon', sa.Float(), nullable=True),
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.CheckConstraint("leg_type IN ('upwind', 'downwind', 'reach')",
                           name=op.f('ck_session_legs_leg_type_allowed')),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'],
                                name=op.f('fk_session_legs_session_id_sessions'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_session_legs')),
    )
    op.create_index(op.f('ix_session_legs_session_id'), 'session_legs',
                    ['session_id'], unique=False)

    op.create_table(
        'session_analysis',
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('correlations', sa.JSON(), nullable=True),
        sa.Column('violin', sa.JSON(), nullable=True),
        sa.Column('maneuver_summary', sa.JSON(), nullable=True),
        sa.Column('leg_comparison', sa.JSON(), nullable=True),
        sa.Column('sensor_stats', sa.JSON(), nullable=True),
        sa.Column('vmg_series', sa.JSON(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'],
                                name=op.f('fk_session_analysis_session_id_sessions'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id', name=op.f('pk_session_analysis')),
    )


def downgrade() -> None:
    op.drop_table('session_analysis')
    op.drop_index(op.f('ix_session_legs_session_id'), table_name='session_legs')
    op.drop_table('session_legs')
    op.drop_index(op.f('ix_session_maneuvers_session_id'), table_name='session_maneuvers')
    op.drop_table('session_maneuvers')
