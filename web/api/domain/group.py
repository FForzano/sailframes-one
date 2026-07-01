"""Group domain model + membership.

A group is a free social grouping, independent of clubs and boats — anyone can
create one and invite others. Speculare to ``Club`` (see ``club.py``): plain
membership feeds the session-visibility filter, ``default_session_visibility``
is inherited by sessions shared with the group. Unlike a club, a group has no
single owner column — ``created_by`` records the author and membership carries a
``role`` (``admin`` can manage; ``member`` is plain), so a group can outlive its
creator with several admins.
"""

from typing import Optional

from .base import DomainModel


class GroupMember(DomainModel):
    user_id: int
    role: str = "member"  # admin | member
    status: str = "active"  # invited | active
    joined_at: Optional[str] = None


class Group(DomainModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    created_by: Optional[int] = None
    default_session_visibility: str = "private"
    created_at: Optional[str] = None
    members: list[GroupMember] = []
