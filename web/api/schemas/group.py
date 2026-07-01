"""Group request DTOs."""

from typing import Optional

from pydantic import BaseModel


class GroupCreateModel(BaseModel):
    name: str
    description: Optional[str] = None
    default_session_visibility: str = "private"


class GroupInviteModel(BaseModel):
    user_id: int
    role: str = "member"  # admin | member
    status: str = "invited"  # invited | active


class GroupJoinModel(BaseModel):
    group_id: int
