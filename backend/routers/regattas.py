"""Regatta endpoints (``/api/regattas*``).

A regatta is a multi-day series grouping race days and races. Cross-entity
reads (its races) go through the repository layer, so this router stays
self-contained.
"""

import uuid

from fastapi import APIRouter, HTTPException, Request

from ..auth import require_admin
from ..schemas import RegattaCreateModel, RegattaUpdateModel
from ._common import now_iso, repos

router = APIRouter(prefix="/api/regattas", tags=["regattas"])


@router.get("")
def list_regattas():
    """List all regattas."""
    return {"regattas": [r.to_dict() for r in repos.regattas.list()]}


@router.get("/{regatta_id}")
def get_regatta(regatta_id: str):
    """Get a regatta with its races."""
    regatta = repos.regattas.get(regatta_id)
    if regatta is None:
        raise HTTPException(404, f"Regatta not found: {regatta_id}")
    races = repos.races.list_summaries(regatta_id=regatta_id)
    return {**regatta.to_dict(), "races": races}


@router.post("")
def create_regatta(regatta: RegattaCreateModel, request: Request):
    """Create a new regatta."""
    require_admin(request)
    now = now_iso()
    return repos.regattas.create({
        "regatta_id": str(uuid.uuid4())[:8],
        "name": regatta.name,
        "venue": regatta.venue,
        "boat_class": regatta.boat_class,
        "start_date": regatta.start_date,
        "end_date": regatta.end_date,
        "race_ids": [],
        "created_at": now,
        "updated_at": now,
    }).to_dict()


@router.patch("/{regatta_id}")
def update_regatta(regatta_id: str, update: RegattaUpdateModel, request: Request):
    """Update a regatta."""
    require_admin(request)
    if repos.regattas.get(regatta_id) is None:
        raise HTTPException(404, f"Regatta not found: {regatta_id}")
    changes = {}
    if update.name is not None:
        changes["name"] = update.name
    if update.venue is not None:
        changes["venue"] = update.venue
    if update.start_date is not None:
        changes["start_date"] = update.start_date
    if update.end_date is not None:
        changes["end_date"] = update.end_date
    changes["updated_at"] = now_iso()
    return repos.regattas.update(regatta_id, changes).to_dict()


@router.delete("/{regatta_id}")
def delete_regatta(regatta_id: str, request: Request):
    """Delete a regatta (does not delete races)."""
    require_admin(request)
    if not repos.regattas.delete(regatta_id):
        raise HTTPException(404, f"Regatta not found: {regatta_id}")
    return {"deleted": regatta_id}
