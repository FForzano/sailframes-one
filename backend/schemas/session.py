"""Session request DTOs (Phase 5 crew/privacy edit)."""

from typing import Optional

from pydantic import BaseModel


class SessionCrewSlotModel(BaseModel):
    user_id: Optional[int] = None
    guest_name: Optional[str] = None
    boat_role: Optional[str] = None


class SessionCrewModel(BaseModel):
    """Edit a session's crew (and optionally claim its boat/visibility).

    ``crew`` replaces the session's crew wholesale. Each slot must set exactly
    one of ``user_id`` / ``guest_name`` (a registered user or a guest)."""

    crew: list[SessionCrewSlotModel] = []
    boat_id: Optional[str] = None
    visibility: Optional[str] = None  # private | group | club | public
    club_id: Optional[int] = None
    group_id: Optional[int] = None


class SessionCreateModel(BaseModel):
    """Manually register a sailing outing.

    ``device_id`` is optional: if set, this upserts the usual device+date
    session (same as the ingest pipeline would attribute); if omitted, a new
    device-less "manual" session is created, meant to be filled in later via
    the GPX upload flow (``POST /api/sessions/{id}/gpx/upload-url`` +
    ``.../complete``)."""

    boat_id: str
    date: str  # YYYY-MM-DD, the date of the outing
    device_id: Optional[str] = None
    name: Optional[str] = None
    crew: list[SessionCrewSlotModel] = []
