"""Club endpoints (``/api/clubs*``).

A club has a single ``owner_user_id`` plus plain membership (``club_members``)
used by the session-visibility filter — separate from the RBAC ``club_admin``
role. Create/invite are authenticated + CSRF-protected; listing is open.
"""

from fastapi import APIRouter, HTTPException, Request

from .. import domain
from ..auth import require_user, verify_csrf
from ..schemas import ClubCreateModel, ClubInviteModel
from ._common import now_iso, repos

router = APIRouter(prefix="/api/clubs", tags=["clubs"])


def _can_manage(club: domain.Club, user) -> bool:
    return user.is_superadmin or club.owner_user_id == user.id


@router.get("")
def list_clubs():
    return {"clubs": [c.to_dict() for c in repos.clubs.list()]}


@router.get("/{club_id}")
def get_club(club_id: int):
    club = repos.clubs.get(club_id)
    if club is None:
        raise HTTPException(404, f"Club not found: {club_id}")
    return club.to_dict()


@router.post("")
def create_club(body: ClubCreateModel, request: Request):
    """Create a club; the caller becomes owner and an active member."""
    verify_csrf(request)
    user = require_user(request)
    club = repos.clubs.save(domain.Club(
        name=body.name,
        owner_user_id=user.id,
        default_session_visibility=body.default_session_visibility,
        created_at=now_iso(),
    ))
    repos.clubs.add_member(club.id, domain.ClubMember(
        user_id=user.id, status="active", joined_at=now_iso(),
    ))
    return repos.clubs.get(club.id).to_dict()


@router.post("/{club_id}/members")
def invite_member(club_id: int, body: ClubInviteModel, request: Request):
    """Invite a user (owner / superadmin only)."""
    verify_csrf(request)
    user = require_user(request)
    club = repos.clubs.get(club_id)
    if club is None:
        raise HTTPException(404, f"Club not found: {club_id}")
    if not _can_manage(club, user):
        raise HTTPException(403, "Not allowed to manage this club")
    if repos.users.get_by_id(body.user_id) is None:
        raise HTTPException(404, f"User not found: {body.user_id}")
    added = repos.clubs.add_member(club_id, domain.ClubMember(
        user_id=body.user_id, status=body.status, joined_at=now_iso(),
    ))
    if not added:
        raise HTTPException(409, "Already a member")
    return repos.clubs.get(club_id).to_dict()


@router.post("/{club_id}/join")
def join_club(club_id: int, request: Request):
    """Caller joins: activates a pending invite, or adds an active membership."""
    verify_csrf(request)
    user = require_user(request)
    club = repos.clubs.get(club_id)
    if club is None:
        raise HTTPException(404, f"Club not found: {club_id}")
    if not repos.clubs.set_member_status(club_id, user.id, "active"):
        repos.clubs.add_member(club_id, domain.ClubMember(
            user_id=user.id, status="active", joined_at=now_iso(),
        ))
    return repos.clubs.get(club_id).to_dict()
