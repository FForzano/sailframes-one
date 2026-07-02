"""Permission checks used by endpoints.

Two imperative guards, mirroring how endpoints already call
``require_admin(request)``:

- ``require_admin(request)`` — broad admin gate.
- ``require_permission(request, key, club_id=...)`` — fine-grained RBAC check.

Identity comes from the ``sf_access`` JWT cookie; roles/permissions live in
Postgres (with optional per-club scope). ``SAILFRAMES_ADMIN_BYPASS``, when set,
short-circuits every check — a dev-only escape hatch.
"""

import hmac
import os
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import select

from .tokens import ACCESS_COOKIE, CSRF_COOKIE, decode_access_token

ADMIN_PERMISSION = "admin"


def current_user(request: Request):
    """Resolve the authenticated user (a ``UserORM``) from the access JWT
    cookie, or ``None`` for anonymous callers. Does NOT raise — use
    ``require_user`` when auth is mandatory."""
    from ..repositories import get_repos

    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    uid = decode_access_token(token)
    if uid is None:
        return None
    return get_repos().users.get_by_id(uid)


def require_user(request: Request):
    """Like ``current_user`` but 401s when unauthenticated."""
    u = current_user(request)
    if u is None:
        raise HTTPException(401, "Authentication required")
    return u


def effective_capabilities(user) -> dict:
    """Capability snapshot for the frontend: roles + effective permissions
    (global vs per-club, mirroring ``_user_has_permission``) + memberships.

    The server still authorizes every mutation — this payload only decides what
    UI to show."""
    from ..repositories import get_repos

    repos = get_repos()

    clubs_owned, clubs_member = [], []
    for c in repos.clubs.list():
        if c.owner_user_id == user.id:
            clubs_owned.append(c.id)
        if repos.clubs.is_active_member(c.id, user.id):
            clubs_member.append(c.id)
    groups = [g.id for g in repos.groups.list() if repos.groups.is_member(g.id, user.id)]
    boats_owner, boats_skipper = [], []
    for b in repos.boats.list():
        if repos.boats.is_member(b.boat_id, user.id, roles=["owner"]):
            boats_owner.append(b.boat_id)
        if repos.boats.is_member(b.boat_id, user.id, roles=["skipper"]):
            boats_skipper.append(b.boat_id)

    roles: list[dict] = []
    perm_global: set[str] = set()
    perm_by_club: dict[str, set[str]] = {}
    from ..db import get_sessionmaker
    from ..db.models import (
        UserORM,
        RoleORM,
        RolePermissionORM,
        PermissionORM,
    )

    with get_sessionmaker()() as s:
        orm = s.get(UserORM, user.id)
        if orm is not None:
            for ur in orm.roles:
                role = s.get(RoleORM, ur.role_id)
                roles.append({
                    "role": role.name if role else str(ur.role_id),
                    "scope_club_id": ur.scope_club_id,
                })
                keys = [
                    k for (k,) in s.query(PermissionORM.key)
                    .join(RolePermissionORM, RolePermissionORM.permission_id == PermissionORM.id)
                    .filter(RolePermissionORM.role_id == ur.role_id)
                    .all()
                ]
                if ur.scope_club_id is None:
                    perm_global.update(keys)
                else:
                    perm_by_club.setdefault(str(ur.scope_club_id), set()).update(keys)

    return {
        "user": user.to_dict(),
        "roles": roles,
        "permissions": {
            "global": sorted(perm_global),
            "byClub": {k: sorted(v) for k, v in perm_by_club.items()},
        },
        "memberships": {
            "clubsOwned": clubs_owned,
            "clubsMember": clubs_member,
            "groups": groups,
            "boatsOwner": boats_owner,
            "boatsSkipper": boats_skipper,
        },
    }


def session_visible_to(session, user) -> bool:
    """Phase 5 visibility rule (operates on the domain ``Session`` +
    ``domain.User`` | None). See docs/user_plan.md → "Controllo accessi".

    Visible when: public; OR the caller owns it / is in its crew; OR the caller
    is standing crew of the attributed boat; OR visibility=club and the caller
    is an active club member; OR visibility=group and the caller is a group
    member; OR the caller is a superadmin. Anonymous callers see only public.
    """
    from ..repositories import get_repos

    if session.visibility == "public":
        return True
    if user is None:
        return False
    if user.is_superadmin:
        return True
    if session.owner_user_id is not None and session.owner_user_id == user.id:
        return True
    if any(c.user_id == user.id for c in (session.crew or [])):
        return True
    repos = get_repos()
    # Standing crew of the attributed boat always sees its own boat's data.
    if session.boat_id is not None and repos.boats.is_member(session.boat_id, user.id):
        return True
    if session.visibility == "club" and session.club_id is not None:
        if repos.clubs.is_active_member(session.club_id, user.id):
            return True
    if session.visibility == "group" and session.group_id is not None:
        if repos.groups.is_member(session.group_id, user.id):
            return True
    return False


def verify_csrf(request: Request) -> None:
    """Double-submit CSRF check, enforced only for cookie-authenticated
    requests. Send ``X-SF-CSRF`` equal to the ``sf_csrf`` cookie on every
    state-changing request."""
    if not request.cookies.get(ACCESS_COOKIE):
        return
    header = request.headers.get("X-SF-CSRF")
    cookie = request.cookies.get(CSRF_COOKIE)
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        raise HTTPException(403, "CSRF check failed")


def _resolve_user(session, email: str):
    from ..db.models import UserORM

    return session.scalars(
        select(UserORM).where(UserORM.email == email, UserORM.is_active.is_(True))
    ).first()


def _user_has_permission(session, user, key: str, club_id: Optional[int]) -> bool:
    from ..db.models import PermissionORM, RolePermissionORM

    if user.is_superadmin:
        return True
    perm = session.scalars(select(PermissionORM).where(PermissionORM.key == key)).first()
    if perm is None:
        return False
    for ur in user.roles:
        # Scoped grant must match the target club; global grant (NULL) always applies.
        if ur.scope_club_id is not None and club_id is not None and ur.scope_club_id != club_id:
            continue
        rp = session.scalars(
            select(RolePermissionORM).where(
                RolePermissionORM.role_id == ur.role_id,
                RolePermissionORM.permission_id == perm.id,
            )
        ).first()
        if rp:
            return True
    return False


def _check_permission(request: Request, key: str, club_id: Optional[int]) -> bool:
    from ..db import get_sessionmaker

    user = current_user(request)
    if user is None:
        raise HTTPException(403, "Authentication required")
    with get_sessionmaker()() as session:
        orm = _resolve_user(session, user.email)
        if orm is None:
            raise HTTPException(403, "Unknown user")
        if _user_has_permission(session, orm, key, club_id):
            return True
    raise HTTPException(403, f"Permission denied: {key}")


def require_permission(request: Request, key: str, *, club_id: Optional[int] = None) -> bool:
    if os.environ.get("SAILFRAMES_ADMIN_BYPASS"):
        return True
    return _check_permission(request, key, club_id)


def require_admin(request: Request) -> bool:
    if os.environ.get("SAILFRAMES_ADMIN_BYPASS"):
        return True
    return _check_permission(request, ADMIN_PERMISSION, None)
