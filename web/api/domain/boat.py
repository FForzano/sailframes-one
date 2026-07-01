"""Boat domain model — a catalog entry persistent across races.

``members`` is the boat's **standing crew** (persistent roster + who may manage
the boat), distinct from a session's actual crew. ``club_id`` is the structured
club reference that supersedes the free-text ``club`` string (kept in dual-read
until the UI migrates). The legacy ``skippers`` list is retained for dual-read
during the migration into ``members``.
"""

from typing import Optional

from pydantic import Field

from .base import DomainModel


class BoatMember(DomainModel):
    user_id: int
    role: str = "crew"  # owner | skipper | crew | viewer
    created_at: Optional[str] = None


class Boat(DomainModel):
    boat_id: str
    name: str = ""
    type: str = ""
    sail_number: str = ""
    club: str = ""
    club_id: Optional[int] = None
    loa_m: Optional[float] = None
    skippers: list[dict] = Field(default_factory=list)
    members: list[BoatMember] = Field(default_factory=list)
    photos: dict = Field(default_factory=dict)
    cert_url: Optional[str] = None
    mbsa_url: Optional[str] = None
    links: list[dict] = Field(default_factory=list)
    notes: str = ""
    polar: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
