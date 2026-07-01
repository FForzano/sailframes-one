"""Club domain model + membership.

``owner_user_id`` is the single owner (distinct from the ``club_admin`` RBAC
role, of which there can be several). ``members`` is plain membership used by
the session-visibility filter — independent of RBAC roles (a ``member`` role
grants permissions; club membership grants *visibility* of club sessions).
``default_session_visibility`` is inherited by sessions organised by the club.
"""

from typing import Optional

from .base import DomainModel


class ClubMember(DomainModel):
    user_id: int
    status: str = "active"  # invited | active
    joined_at: Optional[str] = None


class Club(DomainModel):
    id: Optional[int] = None
    name: str
    owner_user_id: Optional[int] = None
    default_session_visibility: str = "private"
    created_at: Optional[str] = None
    members: list[ClubMember] = []
