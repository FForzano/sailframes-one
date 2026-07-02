"""Race day endpoints (``/api/racedays*``).

A race day is a single day of racing or training, optionally belonging to a
regatta and grouping a set of races.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from ..auth import require_admin
from ..schemas import RaceDayCreateModel, RaceDayUpdateModel
from ._common import now_iso, repos

router = APIRouter(prefix="/api/racedays", tags=["racedays"])


@router.get("")
def list_racedays(regatta_id: Optional[str] = None):
    days = [d for d in repos.racedays.list()]
    if regatta_id:
        days = [d for d in days if d.regatta_id == regatta_id]
    days = sorted(days, key=lambda d: d.date or "")
    return {"race_days": [d.to_dict() for d in days]}


@router.get("/{raceday_id}")
def get_raceday(raceday_id: str):
    day = repos.racedays.get(raceday_id)
    if day is None:
        raise HTTPException(404, f"Race day not found: {raceday_id}")
    return day.to_dict()


@router.post("")
def create_raceday(raceday: RaceDayCreateModel, request: Request):
    require_admin(request)
    now = now_iso()
    return repos.racedays.create({
        "raceday_id": str(uuid.uuid4())[:8],
        "date": raceday.date,
        "type": raceday.type,
        "name": raceday.name or None,
        "regatta_id": raceday.regatta_id or None,
        "race_ids": [],
        "created_at": now,
        "updated_at": now,
    }).to_dict()


@router.patch("/{raceday_id}")
def update_raceday(raceday_id: str, update: RaceDayUpdateModel, request: Request):
    require_admin(request)
    if repos.racedays.get(raceday_id) is None:
        raise HTTPException(404, f"Race day not found: {raceday_id}")
    changes = {}
    if update.date is not None:
        changes["date"] = update.date
    if update.type is not None:
        changes["type"] = update.type
    if update.name is not None:
        changes["name"] = update.name or None
    if update.regatta_id is not None:
        changes["regatta_id"] = update.regatta_id or None
    changes["updated_at"] = now_iso()
    return repos.racedays.update(raceday_id, changes).to_dict()


@router.delete("/{raceday_id}")
def delete_raceday(raceday_id: str, request: Request):
    require_admin(request)
    if not repos.racedays.delete(raceday_id):
        raise HTTPException(404, f"Race day not found: {raceday_id}")
    return {"deleted": raceday_id}
