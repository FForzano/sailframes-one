"""Wind endpoints (``/api/wind``): station catalog + cached observations.

Matrix: stations/observations are pub-readable; writes are system (fetch job)
or superadmin (station registration) — except ``/nearest``, any authenticated
user can trigger an on-demand Open-Meteo lookup/auto-creation for their own
session/race location (see ``services/wind_lookup.py``). The periodic fetch
is triggered on ``/api/system/wind/fetch`` by the wind-scheduler service.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from ..auth import require_superadmin, require_user, verify_csrf
from ..schemas import WindStationWriteModel
from ..services import wind_lookup
from ._common import repos

router = APIRouter(prefix="/api/wind", tags=["wind"])

OBSERVATIONS_DEFAULT_WINDOW_HOURS = 72
OBSERVATIONS_MAX_LIMIT = 1000


def _require_station(station_id: uuid.UUID):
    station = repos.wind.get(station_id)
    if station is None:
        raise HTTPException(404, "Wind station not found")
    return station


@router.get("/stations")
def list_stations(provider: Optional[str] = None):
    return [s.to_dict() for s in repos.wind.list(provider=provider)]


@router.get("/stations/{station_id}")
def get_station(station_id: uuid.UUID):
    return _require_station(station_id).to_dict()


@router.post("/stations")
def create_station(body: WindStationWriteModel, request: Request):
    verify_csrf(request)
    require_superadmin(request)
    if not body.provider or not body.station_type:
        raise HTTPException(422, "provider and station_type are required")
    data = body.model_dump(exclude_unset=True)
    if body.provider == "open_meteo":
        # No real "station id" for a forecast grid — the adapter queries by
        # coordinate, so external_station_id is derived, not user-entered.
        if body.lat is None or body.lng is None:
            raise HTTPException(422, "lat and lng are required for open_meteo")
        data["external_station_id"] = f"{body.lat},{body.lng}"
    elif not body.external_station_id:
        raise HTTPException(422, "external_station_id is required")
    if repos.wind.get_by_provider_external(body.provider, data["external_station_id"]):
        raise HTTPException(409, "Station already registered")
    return repos.wind.create(data).to_dict()


@router.patch("/stations/{station_id}")
def update_station(station_id: uuid.UUID, body: WindStationWriteModel, request: Request):
    verify_csrf(request)
    require_superadmin(request)
    _require_station(station_id)
    return repos.wind.update(station_id, body.model_dump(exclude_unset=True)).to_dict()


@router.delete("/stations/{station_id}")
def delete_station(station_id: uuid.UUID, request: Request):
    verify_csrf(request)
    require_superadmin(request)
    if not repos.wind.delete(station_id):
        raise HTTPException(404, "Wind station not found")
    return {"ok": True}


@router.get("/stations/{station_id}/observations")
def list_observations(station_id: uuid.UUID,
                      start: Optional[datetime] = None,
                      end: Optional[datetime] = None,
                      limit: int = Query(200, le=OBSERVATIONS_MAX_LIMIT, gt=0),
                      offset: int = Query(0, ge=0)):
    """Newest-first, paginated. The cache grows without bound (idempotent
    upsert on every scheduler tick) — defaults to the last 72h when no
    explicit range is given, rather than dumping the whole history."""
    station = _require_station(station_id)
    if start is None and end is None:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=OBSERVATIONS_DEFAULT_WINDOW_HOURS)
    # A range further back than the scheduler/forecast fetch ever covers has no
    # cached rows — the shared primitive backfills from the archive on demand,
    # rather than silently returning nothing (or the wrong-window "latest").
    rows = wind_lookup.list_observations_with_backfill(
        station, start, end, limit=limit, offset=offset)
    return [o.to_dict() for o in rows]


@router.get("/nearest")
def nearest_station(lat: float, lng: float, request: Request, at: Optional[datetime] = None):
    """Get-or-create the best wind station for a coordinate (real sensor
    within 50km, else an existing Open-Meteo grid point within 25km, else a
    freshly auto-created one) — any authenticated user, used by session/race
    pages that have no wind data yet.

    ``at``: pass the session/race's actual time (not "now") so a real sensor
    with no historical data for that date falls through to the Open-Meteo
    grid tier instead of being returned empty-handed — see
    ``services/wind_lookup.find_or_create_station``."""
    require_user(request)
    return wind_lookup.find_or_create_station(lat, lng, at=at).to_dict()
