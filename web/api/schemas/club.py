"""Club request DTOs."""

from typing import Optional

from pydantic import BaseModel


class ClubCreateModel(BaseModel):
    name: str
    default_session_visibility: str = "private"


class ClubInviteModel(BaseModel):
    user_id: int
    status: str = "invited"  # invited | active


class ClubJoinModel(BaseModel):
    club_id: int
