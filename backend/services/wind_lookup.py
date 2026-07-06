"""Nearest-station resolution for sessions/races that have no wind data.

Tiered by provider quality, not raw distance: a real sensor (club-registered
``custom_device``, or a physical ``noaa_ndbc``/``noaa_metar`` station) beats an
Open-Meteo forecast-grid point even if slightly farther, because it reflects
actual local conditions rather than a ~11km-resolution model. Only when no
real sensor is in range do we fall back to an existing grid point, and only
when neither exists do we auto-create one — Open-Meteo is the only provider
that can be pointed at an arbitrary coordinate (NDBC/METAR are real, fixed
installations; a superadmin curates those, see docs/frontend-project.md).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from ..repositories import get_repos
from .wind_providers import PROVIDERS
from .wind_providers import open_meteo

logger = logging.getLogger(__name__)

REAL_SENSOR_PROVIDERS = ("custom_device", "noaa_ndbc", "noaa_metar")
REAL_SENSOR_RADIUS_KM = 50
GRID_RADIUS_KM = 25
# How far around `at` to check for *any* cached observation before trusting a
# real-sensor station for a specific point in time (see `find_or_create_station`).
HISTORICAL_CHECK_WINDOW_HOURS = 24


def _has_observations_near(repos, station_id, at: datetime) -> bool:
    start = at - timedelta(hours=HISTORICAL_CHECK_WINDOW_HOURS)
    end = at + timedelta(hours=HISTORICAL_CHECK_WINDOW_HOURS)
    return len(repos.wind.list_observations(station_id, start=start, end=end, limit=1)) > 0


def find_or_create_station(lat: float, lng: float, at: Optional[datetime] = None):
    """Resolve the best wind station for a coordinate, auto-creating an
    Open-Meteo grid point (and fetching it immediately) if nothing else is
    in range. Returns the ``WindStationORM``.

    ``at``, when given (a session/race's actual time rather than "now"),
    makes the real-sensor tier conditional on actually having data near that
    moment: NOAA buoys/METAR stations have no historical archive, so a sensor
    that's merely nearby but empty for that date would otherwise shadow the
    Open-Meteo grid tier, which *can* backfill any past date on demand (see
    ``routers/wind.py::list_observations``). Real-time lookups (``at=None``)
    are unaffected — they keep preferring the real sensor unconditionally."""
    repos = get_repos()

    station = repos.wind.find_nearest(lat, lng, providers=list(REAL_SENSOR_PROVIDERS),
                                      max_km=REAL_SENSOR_RADIUS_KM)
    if station is not None and (at is None or _has_observations_near(repos, station.id, at)):
        return station

    station = repos.wind.find_nearest(lat, lng, providers=["open_meteo"], max_km=GRID_RADIUS_KM)
    if station is not None:
        return station

    station = repos.wind.create({
        "provider": "open_meteo",
        "external_station_id": f"{lat},{lng}",
        "station_type": "forecast_grid",
        "lat": lat,
        "lng": lng,
    })
    # Fetch inline so the caller doesn't have to wait for the next scheduler
    # tick — one HTTP call, ~1s; failures are non-fatal (the scheduler retries).
    try:
        rows = PROVIDERS["open_meteo"](station.external_station_id)
        repos.wind.upsert_observations(station.id, rows)
    except Exception:
        logger.warning("open_meteo immediate fetch failed for new station %s", station.id,
                       exc_info=True)
    return station


def backfill_historical(station, start: datetime, end: datetime) -> None:
    """Fetch and cache past observations for a date range the periodic
    scheduler never covered — e.g. a session imported for a date older than
    the forecast endpoint's ``past_days`` window. Only ``open_meteo`` has a
    historical archive API; real sensors (NDBC/METAR) have no equivalent, so
    gaps there stay gaps. Failures are non-fatal: the caller just returns
    whatever was already cached."""
    if station.provider != "open_meteo":
        return
    repos = get_repos()
    try:
        rows = open_meteo.fetch_historical(
            station.external_station_id, start.date().isoformat(), end.date().isoformat()
        )
        repos.wind.upsert_observations(station.id, rows)
    except Exception:
        logger.warning("open_meteo historical backfill failed for station %s", station.id,
                       exc_info=True)


__all__ = ["find_or_create_station", "backfill_historical", "REAL_SENSOR_PROVIDERS"]
