"""Group endpoints (``/api/groups*``).

Free social groups, independent of clubs and boats — anyone can create one, the
creator becomes an ``admin`` member. Plain membership (``group_members``) feeds
the session-visibility filter; the ``admin`` role (not a single owner) grants
management. Create/invite/join are authenticated + CSRF-protected. Listing is
open, but ``?member=me`` narrows to the caller's own groups (and requires auth).
"""

from fastapi import APIRouter, HTTPException, Request

from .. import domain
from ..auth import require_user, verify_csrf
from ..schemas import GroupCreateModel, GroupInviteModel
from ._common import now_iso, repos

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _is_active_admin(group: domain.Group, user) -> bool:
    return any(
        m.user_id == user.id and m.role == "admin" and m.status == "active"
        for m in group.members
    )


def _can_manage(group: domain.Group, user) -> bool:
    return user.is_superadmin or _is_active_admin(group, user)


@router.get("")
def list_groups(request: Request, member: str = ""):
    """List all groups, or only the caller's own with ``?member=me``."""
    if member == "me":
        user = require_user(request)
        return {"groups": [
            g.to_dict() for g in repos.groups.list()
            if repos.groups.is_member(g.id, user.id)
        ]}
    return {"groups": [g.to_dict() for g in repos.groups.list()]}


@router.get("/{group_id}")
def get_group(group_id: int):
    group = repos.groups.get(group_id)
    if group is None:
        raise HTTPException(404, f"Group not found: {group_id}")
    return group.to_dict()


@router.post("")
def create_group(body: GroupCreateModel, request: Request):
    """Create a group; the caller becomes an active ``admin`` member."""
    verify_csrf(request)
    user = require_user(request)
    group = repos.groups.save(domain.Group(
        name=body.name,
        description=body.description,
        created_by=user.id,
        default_session_visibility=body.default_session_visibility,
        created_at=now_iso(),
    ))
    repos.groups.add_member(group.id, domain.GroupMember(
        user_id=user.id, role="admin", status="active", joined_at=now_iso(),
    ))
    return repos.groups.get(group.id).to_dict()


@router.post("/{group_id}/members")
def invite_member(group_id: int, body: GroupInviteModel, request: Request):
    """Invite a user (group admin / superadmin only)."""
    verify_csrf(request)
    user = require_user(request)
    group = repos.groups.get(group_id)
    if group is None:
        raise HTTPException(404, f"Group not found: {group_id}")
    if not _can_manage(group, user):
        raise HTTPException(403, "Not allowed to manage this group")
    if repos.users.get_by_id(body.user_id) is None:
        raise HTTPException(404, f"User not found: {body.user_id}")
    added = repos.groups.add_member(group_id, domain.GroupMember(
        user_id=body.user_id, role=body.role, status=body.status, joined_at=now_iso(),
    ))
    if not added:
        raise HTTPException(409, "Already a member")
    return repos.groups.get(group_id).to_dict()


@router.post("/{group_id}/join")
def join_group(group_id: int, request: Request):
    """Caller joins: activates a pending invite, or adds an active membership."""
    verify_csrf(request)
    user = require_user(request)
    group = repos.groups.get(group_id)
    if group is None:
        raise HTTPException(404, f"Group not found: {group_id}")
    if not repos.groups.set_member_status(group_id, user.id, "active"):
        repos.groups.add_member(group_id, domain.GroupMember(
            user_id=user.id, role="member", status="active", joined_at=now_iso(),
        ))
    return repos.groups.get(group_id).to_dict()
