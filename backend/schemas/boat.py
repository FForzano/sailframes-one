"""Boat request DTOs: boats, user_boats membership, boat_classes."""

import uuid
from typing import Optional

from pydantic import BaseModel


class BoatWriteModel(BaseModel):
    name: Optional[str] = None  # required on create, enforced by the router
    boat_class_id: Optional[uuid.UUID] = None
    sail_number: Optional[str] = None
    loa_m: Optional[float] = None
    notes: Optional[str] = None
    club_id: Optional[uuid.UUID] = None


class BoatMemberModel(BaseModel):
    user_id: uuid.UUID
    role: str = "visitor"  # owner | admin | visitor
    default_sailing_role: Optional[str] = None  # skipper | crew


class BoatMemberRoleModel(BaseModel):
    role: str


class BoatClassWriteModel(BaseModel):
    name: Optional[str] = None  # required on create, enforced by the router
    description: Optional[str] = None
    loa_m: Optional[float] = None
    beam_m: Optional[float] = None
    sail_area_sqm: Optional[float] = None
    crew_size: Optional[int] = None
    hull_type: Optional[str] = None  # monohull | multihull
    rig_type: Optional[str] = None  # sloop | una (RYA "Rig" column: S/U)
    spinnaker_type: Optional[str] = None  # none | asymmetric | symmetric (RYA "Spinnaker": 0/A/C)
    py_rating: Optional[int] = None  # RYA "Number" column
    rya_class_id: Optional[int] = None  # official RYA Class ID, reference only
