"""Boat catalog endpoints (``/api/boats*``).

Read-only listing + single fetch, plus (Phase 2) write endpoints for boat
ownership and **standing crew** (``boat_members``, distinct from a session's
actual crew). These are the first mutating endpoints on boats — modelled on the
regatta router style. Mutations are CSRF-protected and gated on boat membership
(owner/skipper) or the ``boat.edit`` RBAC permission / superadmin.
"""

from fastapi import APIRouter, HTTPException, Request

from .. import domain
from ..auth import require_permission, require_user, verify_csrf
from ..schemas import BoatMemberModel, BoatMemberRoleModel, BoatWriteModel
from ._common import now_iso, repos

router = APIRouter(prefix="/api/boats", tags=["boats"])

# Roles that may manage a boat (edit it + its roster).
MANAGE_ROLES = ["owner", "skipper"]


def _has_boat_edit_permission(request: Request) -> bool:
    """True if the caller holds the ``boat.edit`` RBAC permission (or is an
    admin via bypass/Cloudflare/superadmin). Non-raising wrapper around
    ``require_permission`` so it composes with the membership check."""
    try:
        return require_permission(request, "boat.edit")
    except HTTPException:
        return False


def _can_manage(boat_id: str, user, request: Request) -> bool:
    if user.is_superadmin:
        return True
    if repos.boats.is_member(boat_id, user.id, roles=MANAGE_ROLES):
        return True
    return _has_boat_edit_permission(request)


@router.get("")
def list_boats():
    """List all boat profiles."""
    return {"boats": [b.to_dict() for b in repos.boats.list()]}


@router.get("/{boat_id}")
def get_boat(boat_id: str):
    """Get a specific boat profile."""
    boat = repos.boats.get(boat_id)
    if boat is None:
        raise HTTPException(404, f"Boat not found: {boat_id}")
    return boat.to_dict()


@router.post("")
def create_boat(body: BoatWriteModel, request: Request):
    """Create a boat; the caller becomes its ``owner`` standing-crew member."""
    verify_csrf(request)
    user = require_user(request)
    if not body.boat_id:
        raise HTTPException(422, "boat_id is required")
    if repos.boats.get(body.boat_id) is not None:
        raise HTTPException(409, f"Boat already exists: {body.boat_id}")
    now = now_iso()
    boat = repos.boats.save(domain.Boat(
        boat_id=body.boat_id,
        name=body.name or "",
        type=body.type or "",
        sail_number=body.sail_number or "",
        club=body.club or "",
        club_id=body.club_id,
        loa_m=body.loa_m,
        notes=body.notes or "",
        created_at=now,
        updated_at=now,
    ))
    repos.boats.add_member(boat.boat_id, domain.BoatMember(
        user_id=user.id, role="owner", created_at=now,
    ))
    return repos.boats.get(boat.boat_id).to_dict()


@router.patch("/{boat_id}")
def update_boat(boat_id: str, body: BoatWriteModel, request: Request):
    """Edit a boat (owner/skipper of the boat, ``boat.edit`` permission, or
    superadmin). Only provided fields are applied. Sets ``club_id`` too."""
    verify_csrf(request)
    user = require_user(request)
    boat = repos.boats.get(boat_id)
    if boat is None:
        raise HTTPException(404, f"Boat not found: {boat_id}")
    if not _can_manage(boat_id, user, request):
        raise HTTPException(403, "Not allowed to manage this boat")
    fields = body.model_dump(exclude_unset=True, exclude={"boat_id"})
    for key, value in fields.items():
        setattr(boat, key, value)
    boat.updated_at = now_iso()
    return repos.boats.save(boat).to_dict()


@router.get("/{boat_id}/members")
def list_members(boat_id: str):
    """List a boat's standing crew."""
    if repos.boats.get(boat_id) is None:
        raise HTTPException(404, f"Boat not found: {boat_id}")
    return {"members": [m.to_dict() for m in repos.boats.list_members(boat_id)]}


@router.post("/{boat_id}/members")
def add_member(boat_id: str, body: BoatMemberModel, request: Request):
    """Add a standing-crew member (owner/skipper of the boat or admin)."""
    verify_csrf(request)
    user = require_user(request)
    boat = repos.boats.get(boat_id)
    if boat is None:
        raise HTTPException(404, f"Boat not found: {boat_id}")
    if not _can_manage(boat_id, user, request):
        raise HTTPException(403, "Not allowed to manage this boat")
    if repos.users.get_by_id(body.user_id) is None:
        raise HTTPException(404, f"User not found: {body.user_id}")
    added = repos.boats.add_member(boat_id, domain.BoatMember(
        user_id=body.user_id, role=body.role, created_at=now_iso(),
    ))
    if not added:
        raise HTTPException(409, "Already a member")
    return repos.boats.get(boat_id).to_dict()


@router.patch("/{boat_id}/members/{user_id}")
def set_member_role(boat_id: str, user_id: int, body: BoatMemberRoleModel, request: Request):
    """Change a member's role (owner/skipper of the boat or admin)."""
    verify_csrf(request)
    user = require_user(request)
    boat = repos.boats.get(boat_id)
    if boat is None:
        raise HTTPException(404, f"Boat not found: {boat_id}")
    if not _can_manage(boat_id, user, request):
        raise HTTPException(403, "Not allowed to manage this boat")
    if not repos.boats.set_member_role(boat_id, user_id, body.role):
        raise HTTPException(404, f"Member not found: {user_id}")
    return repos.boats.get(boat_id).to_dict()


@router.delete("/{boat_id}/members/{user_id}")
def remove_member(boat_id: str, user_id: int, request: Request):
    """Remove a standing-crew member (owner/skipper of the boat or admin)."""
    verify_csrf(request)
    user = require_user(request)
    boat = repos.boats.get(boat_id)
    if boat is None:
        raise HTTPException(404, f"Boat not found: {boat_id}")
    if not _can_manage(boat_id, user, request):
        raise HTTPException(403, "Not allowed to manage this boat")
    if not repos.boats.remove_member(boat_id, user_id):
        raise HTTPException(404, f"Member not found: {user_id}")
    return repos.boats.get(boat_id).to_dict()
