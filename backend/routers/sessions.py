"""Session metadata + management endpoints (``/api/sessions*``).

Sessions are recorded-data manifests (one device, one date); the bulk sensor
payloads stay in the blob store. This router covers listing, single fetch,
deletion, creation (device-attributed or fully manual + GPX upload), and the
bulk cleanup of short/unassigned sessions.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from ..auth import (
    current_user,
    require_admin,
    require_user,
    session_visible_to,
    verify_csrf,
)
from ..schemas import SessionCreateModel, SessionCrewModel
from ._common import (
    DATA_PREFIX,
    delete_prefix,
    list_keys,
    load_json_or_404,
    repos,
    blob,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Standing-crew roles on a boat that may edit its sessions' crew/attribution.
BOAT_MANAGE_ROLES = ["owner", "skipper"]


def _crew_dicts(slots) -> list[dict]:
    crew = []
    for slot in slots:
        if (slot.user_id is None) == (slot.guest_name is None):
            raise HTTPException(422, "Each crew slot needs exactly one of user_id / guest_name")
        crew.append({"user_id": slot.user_id, "guest_name": slot.guest_name, "boat_role": slot.boat_role})
    return crew


@router.get("")
def list_sessions(request: Request):
    """List race sessions visible to the caller.

    Stays open (no auth required) but the response is **filtered** by the
    visibility rule: an anonymous caller sees only ``public`` sessions; a
    logged-in caller also sees their own / crewed / club / group ones. Historical
    sessions backfilled to ``public`` keep showing, so the public dashboard is
    unaffected."""
    user = current_user(request)
    sessions = []
    for s in repos.sessions.list():
        if not session_visible_to(s, user):
            continue
        duration_sec = s.duration_sec or 0
        sessions.append({
            "id": s.id,
            "device_id": s.device_id,
            "date": s.date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "duration_sec": duration_sec,
            "duration_minutes": round(duration_sec / 60) if duration_sec else 0,
            "sensors": s.sensors if s.sensors is not None else [],
            "has_video": s.has_video,
            "has_analysis": s.has_analysis,
            "boat": s.boat,
            "name": s.name,
            "session_id": s.session_id,
            "visibility": s.visibility,
            "boat_id": s.boat_id,
            "source": s.source,
            "processing_status": s.processing_status,
        })

    return {"sessions": sorted(sessions, key=lambda s: s["date"], reverse=True)}


@router.post("")
def create_session(body: SessionCreateModel, request: Request):
    """Register a sailing outing: boat + crew, and either an existing device
    (claims/edits that device's session for the given date — 404 if it hasn't
    uploaded anything yet) or nothing (creates a device-less "manual" session,
    to be filled in via the GPX upload flow below). Any standing crew member of
    the boat may create a session for it (not just owner/skipper)."""
    verify_csrf(request)
    user = require_user(request)
    if not repos.boats.is_member(body.boat_id, user.id):
        raise HTTPException(403, "Not a member of this boat")

    crew = _crew_dicts(body.crew)

    if body.device_id:
        repos.sessions.attribute_boat(body.device_id, body.date, body.boat_id)
        updated = repos.sessions.edit(
            body.device_id, body.date, crew=crew, boat_id=body.boat_id, claim_owner_id=user.id,
        )
        if updated is None:
            raise HTTPException(
                404,
                "No data uploaded yet for that device on that date. Create the "
                "session without a device and upload a GPX track instead, or "
                "try again once the device has synced.",
            )
        return updated.to_dict()

    session = repos.sessions.create_manual(
        boat_id=body.boat_id, date=body.date, name=body.name, crew=crew, owner_user_id=user.id,
    )
    return session.to_dict()


@router.get("/id/{session_id}")
def get_session_by_id(session_id: int, request: Request):
    """Get a session by its surrogate id — the only way to address a
    device-less "manual" session (it has no device_id/date pair)."""
    session = repos.sessions.get_by_id(session_id)
    if session is None:
        raise HTTPException(404, f"Session not found: {session_id}")
    if not session_visible_to(session, current_user(request)):
        raise HTTPException(404, f"Session not found: {session_id}")
    return session.to_dict()


@router.get("/{device_id}/{date}")
def get_session(device_id: str, date: str, request: Request):
    """Get session metadata and manifest (subject to the visibility rule)."""
    session = repos.sessions.get(device_id, date)
    if session is None:
        raise HTTPException(404, f"Session not found: {device_id}/{date}")
    if not session_visible_to(session, current_user(request)):
        # 404 (not 403) so a private session isn't even confirmed to exist.
        raise HTTPException(404, f"Session not found: {device_id}/{date}")
    return session.to_dict()


def _can_edit_session(session, device_id, user) -> bool:
    """Owner/skipper of the attributed boat, whoever registered the device (for
    an unclaimed session), the session owner, or a superadmin."""
    if user.is_superadmin:
        return True
    if session.owner_user_id is not None and session.owner_user_id == user.id:
        return True
    if session.boat_id is not None and repos.boats.is_member(
        session.boat_id, user.id, roles=BOAT_MANAGE_ROLES
    ):
        return True
    if session.owner_user_id is None:
        device = repos.devices.get(device_id)
        if device is not None and device.registered_by == user.id:
            return True
    return False


@router.patch("/{device_id}/{date}/crew")
def edit_session_crew(device_id: str, date: str, body: SessionCrewModel, request: Request):
    """Edit a session's crew (guests allowed) and optionally claim its boat /
    set visibility. Writes to the deploy's authoritative store via the repo."""
    verify_csrf(request)
    user = require_user(request)
    session = repos.sessions.get(device_id, date)
    if session is None:
        raise HTTPException(404, f"Session not found: {device_id}/{date}")
    if not _can_edit_session(session, device_id, user):
        raise HTTPException(403, "Not allowed to edit this session")

    crew = []
    for slot in body.crew:
        if (slot.user_id is None) == (slot.guest_name is None):
            raise HTTPException(422, "Each crew slot needs exactly one of user_id / guest_name")
        crew.append({"user_id": slot.user_id, "guest_name": slot.guest_name, "boat_role": slot.boat_role})
    updated = repos.sessions.edit(
        device_id, date, crew=crew, boat_id=body.boat_id, visibility=body.visibility,
        club_id=body.club_id, group_id=body.group_id, claim_owner_id=user.id,
    )
    return updated.to_dict()


def _manual_session_or_404(session_id: int, user):
    session = repos.sessions.get_by_id(session_id)
    if session is None or session.source != "manual":
        raise HTTPException(404, f"Session not found: {session_id}")
    if not _can_edit_session(session, None, user):
        raise HTTPException(403, "Not allowed to upload to this session")
    return session


@router.post("/{session_id}/gpx/upload-url")
def get_gpx_upload_url(session_id: int, request: Request):
    """Get a URL the caller can PUT the raw GPX file to directly (S3 presigned
    PUT, or the ``/api/uploads`` proxy on MinIO/local — see
    ``BlobStore.upload_ref``). Only for manual (device-less) sessions."""
    verify_csrf(request)
    user = require_user(request)
    _manual_session_or_404(session_id, user)

    key = f"raw/manual/{session_id}/track.gpx"
    url = blob.upload_ref(key, content_type="application/gpx+xml")
    return {"url": url, "key": key, "method": "PUT"}


@router.post("/{session_id}/gpx/complete")
def complete_gpx_upload(session_id: int, background_tasks: BackgroundTasks, request: Request):
    """Call after the PUT to the upload URL succeeds: verifies the object
    landed, then schedules GPX-parse + analysis in the background and returns
    immediately. Poll ``GET /api/sessions/id/{id}`` for ``processing_status``."""
    verify_csrf(request)
    user = require_user(request)
    _manual_session_or_404(session_id, user)

    key = f"raw/manual/{session_id}/track.gpx"
    if not blob.exists(key):
        raise HTTPException(400, "No GPX file found at the upload URL — upload it first")

    repos.sessions.set_processing_status(session_id, "processing")

    from ..services.gpx_processing import process_manual_session_gpx
    background_tasks.add_task(process_manual_session_gpx, session_id)

    return {"status": "processing", "id": session_id}


@router.delete("/{device_id}/{date}")
def delete_session(device_id: str, date: str, request: Request):
    """Delete a session and all its data (processed folder)."""
    require_admin(request)
    prefix = f"{DATA_PREFIX}/{device_id}/{date}/"
    deleted_count = delete_prefix(prefix)

    if deleted_count == 0:
        raise HTTPException(404, f"Session not found: {device_id}/{date}")

    return {
        "status": "deleted",
        "device_id": device_id,
        "date": date,
        "files_deleted": deleted_count,
    }


@router.post("/cleanup")
def cleanup_sessions(
    request: Request,
    max_duration_minutes: int = Query(15, description="Delete sessions shorter than this"),
    require_boat: bool = Query(True, description="Delete sessions with no boat selected"),
    dry_run: bool = Query(True, description="Preview without deleting"),
):
    """Bulk delete sessions that are too short or have no boat assigned.

    By default runs in dry_run mode - set dry_run=false to actually delete.
    """
    require_admin(request)
    # Get all sessions
    keys = list_keys(f"{DATA_PREFIX}/")
    manifests = [k for k in keys if k.endswith("manifest.json")]

    to_delete = []
    kept = []

    for key in manifests:
        try:
            parts = key.split("/")
            device_id = parts[1] if len(parts) > 2 else "unknown"
            date = parts[2] if len(parts) > 2 else "unknown"
            if device_id == "manual":
                # Manual/GPX sessions are DB-owned rows, not device+date pairs.
                continue
            manifest = load_json_or_404(key)

            duration_sec = manifest.get("duration_sec", 0)
            duration_minutes = duration_sec / 60 if duration_sec else 0
            boat = manifest.get("boat")

            should_delete = False
            reason = []

            # Check duration
            if duration_minutes < max_duration_minutes:
                should_delete = True
                reason.append(f"duration {duration_minutes:.1f}min < {max_duration_minutes}min")

            # Check boat (only if require_boat is True and session is long enough)
            if require_boat and not boat and duration_minutes >= max_duration_minutes:
                should_delete = True
                reason.append("no boat selected")

            session_info = {
                "device_id": device_id,
                "date": date,
                "duration_minutes": round(duration_minutes, 1),
                "boat": boat,
                "name": manifest.get("name"),
            }

            if should_delete:
                session_info["reason"] = ", ".join(reason)
                to_delete.append(session_info)
            else:
                kept.append(session_info)

        except Exception:
            continue

    deleted_count = 0
    if not dry_run:
        for session in to_delete:
            prefix = f"{DATA_PREFIX}/{session['device_id']}/{session['date']}/"
            deleted_count += delete_prefix(prefix)

    return {
        "dry_run": dry_run,
        "criteria": {
            "max_duration_minutes": max_duration_minutes,
            "require_boat": require_boat,
        },
        "to_delete": to_delete,
        "to_delete_count": len(to_delete),
        "kept_count": len(kept),
        "files_deleted": deleted_count if not dry_run else 0,
    }
