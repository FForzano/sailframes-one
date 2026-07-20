"""Add finish-line mark roles (``finish_pin``/``finish_rc``) to ``marks``.

Mirrors ``pin``/``rc`` (own pair of marks) rather than reusing them, since a
course can finish on a different line than it started — the frontend offers
a "same as start" convenience that copies pin/rc's coordinates into these
when the two lines do coincide (see ``db/models/activity.py`` MARK_ROLES).

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-20
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0030'
down_revision: Union[str, None] = '0029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('mark_role_allowed', 'marks', type_='check')
    op.create_check_constraint(
        'mark_role_allowed', 'marks',
        "mark_role IN ('pin', 'rc', 'windward', 'leeward', 'gate_port', 'gate_stbd', "
        "'offset', 'drill', 'finish_pin', 'finish_rc')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM marks WHERE mark_role IN ('finish_pin', 'finish_rc')")
    op.drop_constraint('mark_role_allowed', 'marks', type_='check')
    op.create_check_constraint(
        'mark_role_allowed', 'marks',
        "mark_role IN ('pin', 'rc', 'windward', 'leeward', 'gate_port', 'gate_stbd', "
        "'offset', 'drill')",
    )
