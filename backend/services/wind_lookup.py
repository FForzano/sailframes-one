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
# Real sensors are few and fixed, so a generous radius makes sense; Open-Meteo
# is a free grid query, so there's no reason to reuse a point that's actually
# many km from the boat — a tight radius keeps grid stations meaningfully
# local (a session near the coast shouldn't share a point with one out in
# open water) while still deduplicating stations for boats sailing the same
# stretch of water.
GRID_RADIUS_KM = 3
# How far around `at` to check for *any* cached observation before trusting a
# real-sensor station for a specific point in time (see `find_or_create_station`).
HISTORICAL_CHECK_WINDOW_HOURS = 24
# Open-Meteo's archive endpoint serves ERA5T preliminary reanalysis, which
# lags a few days behind real time before it's available — forecast-sourced
# rows older than this are candidates for reconciliation (see
# `reconcile_forecasts`).
RECONCILE_DELAY_DAYS = 3


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


def list_observations_with_backfill(station, start: datetime, end: datetime,
                                    *, limit: int = 500, offset: int = 0):
    """List a station's cached observations in ``[start, end]`` (newest-first),
    backfilling from the historical archive once if the cache is empty for a
    window that predates the periodic scheduler's coverage. The shared read
    primitive behind both ``routers/wind.py`` and ``observations_in_window``."""
    from datetime import timezone

    repos = get_repos()
    rows = repos.wind.list_observations(station.id, start=start, end=end,
                                        limit=limit, offset=offset)
    if not rows and end < datetime.now(timezone.utc) - timedelta(
            hours=HISTORICAL_CHECK_WINDOW_HOURS):
        backfill_historical(station, start, end)
        rows = repos.wind.list_observations(station.id, start=start, end=end,
                                            limit=limit, offset=offset)
    return rows


def observations_in_window(lat: float, lng: float, start: datetime, end: datetime,
                           *, limit: int = 500):
    """Resolve the best station for a coordinate and return ``(station, rows)``
    for ``[start, end]``. Used by the ingestion pipeline to pre-fetch a
    session's wind (with historical backfill) before dispatching analysis."""
    station = find_or_create_station(lat, lng, at=start)
    rows = list_observations_with_backfill(station, start, end, limit=limit)
    return station, rows


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


def reconcile_forecasts() -> dict:
    """Replace provisional Open-Meteo forecast readings with the archive's
    settled (reanalysis) values, for rows old enough that the archive should
    have caught up (``RECONCILE_DELAY_DAYS``). Triggered periodically by the
    wind-scheduler service (``routers/system.py::wind_reconcile``) — one
    archive call per station covering its whole stale range, idempotent
    (overwrites the same rows again harmlessly if re-run)."""
    from datetime import timezone

    repos = get_repos()
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECONCILE_DELAY_DAYS)
    rows_written = 0
    errors: list[str] = []
    for station_id in repos.wind.stations_with_stale_forecasts(cutoff):
        station = repos.wind.get(station_id)
        if station is None or station.provider != "open_meteo":
            continue
        span = repos.wind.stale_forecast_range(station_id, cutoff)
        if span is None:
            continue
        start, end = span
        try:
            rows = open_meteo.fetch_historical(
                station.external_station_id, start.date().isoformat(), end.date().isoformat()
            )
            rows_written += repos.wind.reconcile_observations(station_id, rows)
        except Exception as exc:
            logger.warning("open_meteo reconciliation failed for station %s", station_id,
                           exc_info=True)
            errors.append(f"{station_id}: {exc}")
    return {"rows_reconciled": rows_written, "errors": errors}


__all__ = ["find_or_create_station", "observations_in_window",
           "list_observations_with_backfill", "backfill_historical",
           "reconcile_forecasts", "REAL_SENSOR_PROVIDERS"]
