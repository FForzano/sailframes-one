"""Boat request DTOs (write endpoints + standing-crew management)."""

from typing import Optional

from pydantic import BaseModel


class BoatWriteModel(BaseModel):
    """Create/edit a boat. On create, ``boat_id`` is required; on PATCH every
    field is optional (only provided fields are applied)."""

    boat_id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    sail_number: Optional[str] = None
    club: Optional[str] = None
    club_id: Optional[int] = None
    loa_m: Optional[float] = None
    notes: Optional[str] = None


class BoatMemberModel(BaseModel):
    """Add / update a standing-crew member."""

    user_id: int
    role: str = "crew"  # owner | skipper | crew | viewer


class BoatMemberRoleModel(BaseModel):
    role: str  # owner | skipper | crew | viewer
