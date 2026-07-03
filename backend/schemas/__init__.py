"""API request DTOs (Pydantic) for the SailFrames HTTP layer.

These validate the *request* bodies endpoints accept. Responses are produced by
``ORM.to_dict()`` (see ``db/base.py``), so there is no parallel response-model
layer to keep in sync.
"""

from .regatta import RegattaCreateModel, RegattaUpdateModel
from .raceday import RaceDayCreateModel, RaceDayUpdateModel
from .race import (
    StartFinishLineModel,
    MarkModel,
    RaceBoatModel,
    RaceCreateModel,
    RaceUpdateModel,
)
from .auth import RegisterModel, LoginModel
from .club import ClubCreateModel, ClubInviteModel, ClubJoinModel
from .group import GroupCreateModel, GroupInviteModel, GroupJoinModel
from .device import DeviceRegisterModel, DeviceAssignmentModel
from .session import SessionCrewModel, SessionCrewSlotModel, SessionCreateModel
from .boat import BoatWriteModel, BoatMemberModel, BoatMemberRoleModel

__all__ = [
    "RegattaCreateModel",
    "RegattaUpdateModel",
    "RaceDayCreateModel",
    "RaceDayUpdateModel",
    "StartFinishLineModel",
    "MarkModel",
    "RaceBoatModel",
    "RaceCreateModel",
    "RaceUpdateModel",
    "RegisterModel",
    "LoginModel",
    "ClubCreateModel",
    "ClubInviteModel",
    "ClubJoinModel",
    "GroupCreateModel",
    "GroupInviteModel",
    "GroupJoinModel",
    "DeviceRegisterModel",
    "DeviceAssignmentModel",
    "SessionCrewModel",
    "SessionCrewSlotModel",
    "SessionCreateModel",
    "BoatWriteModel",
    "BoatMemberModel",
    "BoatMemberRoleModel",
]
