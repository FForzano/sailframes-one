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
from typing import Optional

from ..repositories import get_repos
from .wind_providers import PROVIDERS

logger = logging.getLogger(__name__)

REAL_SENSOR_PROVIDERS = ("custom_device", "noaa_ndbc", "noaa_metar")
REAL_SENSOR_RADIUS_KM = 50
GRID_RADIUS_KM = 25


def find_or_create_station(lat: float, lng: float):
    """Resolve the best wind station for a coordinate, auto-creating an
    Open-Meteo grid point (and fetching it immediately) if nothing else is
    in range. Returns the ``WindStationORM``."""
    repos = get_repos()

    station = repos.wind.find_nearest(lat, lng, providers=list(REAL_SENSOR_PROVIDERS),
                                      max_km=REAL_SENSOR_RADIUS_KM)
    if station is not None:
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


__all__ = ["find_or_create_station", "REAL_SENSOR_PROVIDERS"]
