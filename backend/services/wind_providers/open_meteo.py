"""Open-Meteo adapter — global forecast grid, no API key required.

Unlike NDBC (real buoys, USA-only), Open-Meteo has no "station id": every
point on the globe is queried by lat/lng. So ``external_station_id`` carries
no meaning for this provider — the station's ``lat``/``lng`` columns are the
real key, and ``fetch_station`` needs them, not an id string. To fit the
``PROVIDERS`` registry's ``fetch(external_station_id)`` shape, the caller
(``routers/system.py``) passes ``lat,lng`` packed into ``external_station_id``
as ``"{lat},{lng}"`` (enforced by ``routers/wind.py`` on create for this
provider).
"""

from datetime import datetime, timezone

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Historical archive — separate from the forecast endpoint above, needed to
# backfill sessions dated further back than the forecast endpoint's
# `past_days` window covers (see `fetch_historical`).
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FETCH_TIMEOUT_S = 15

MS_TO_KTS = 1.94384

HOURLY_PARAM = "wind_speed_10m,wind_direction_10m,wind_gusts_10m"

# Tried finest-first, each restricted to its own regional domain — Open-Meteo
# returns nulls (not an error) for a point outside a model's coverage, so we
# just try the next one. The forecast endpoint's own "best_match" (omitting
# `models`) already does something similar for *live* data, picking a fine
# regional model automatically — but the *archive* endpoint's implicit
# default is the coarse ~31km ERA5 reanalysis regardless of location, which
# is why this list matters most for `fetch_historical`/reconciliation.
# Verified empirically (see the wind_lookup conversation): all four resolve
# on both endpoints; `icon_d2`/`icon_eu` alone gave a 20°+ different wind
# direction than the archive default for the same Adriatic coastal point.
MODEL_CANDIDATES = (
    "icon_d2",       # DWD ICON-D2, ~2km — Central Europe (covers the Adriatic)
    "icon_eu",       # DWD ICON-EU, ~7km — wider Europe
    "gfs_seamless",  # NOAA GFS+HRRR blend, ~3-13km — better resolution in the US
    "ecmwf_ifs025",  # ECMWF IFS, ~28km — solid global fallback
)


def _parse_latlng(external_station_id: str) -> "tuple[float, float]":
    try:
        lat_s, lng_s = external_station_id.split(",")
        return float(lat_s), float(lng_s)
    except ValueError:
        raise ValueError(
            f"open_meteo external_station_id must be 'lat,lng', got {external_station_id!r}"
        )


def _fetch_best_model(url: str, lat: float, lng: float, extra_params: dict) -> dict:
    """Try each regional model finest-first, returning the first one that
    actually covers this point (non-null wind data); falls back to Open-
    Meteo's own default (no ``models`` param) if none of them do — e.g. the
    middle of an ocean far from every regional domain."""
    base_params = {
        "latitude": lat,
        "longitude": lng,
        "hourly": HOURLY_PARAM,
        "wind_speed_unit": "ms",
        **extra_params,
    }
    for model in MODEL_CANDIDATES:
        try:
            resp = requests.get(url, params={**base_params, "models": model},
                                timeout=FETCH_TIMEOUT_S)
            resp.raise_for_status()
            hourly = resp.json().get("hourly", {})
        except requests.RequestException:
            continue
        if any(v is not None for v in hourly.get("wind_speed_10m", [])):
            return hourly
    resp = requests.get(url, params=base_params, timeout=FETCH_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json().get("hourly", {})


def _rows_from_hourly(hourly: dict, *, is_forecast: bool) -> "list[dict]":
    times = hourly.get("time", [])
    speeds = hourly.get("wind_speed_10m", [])
    dirs = hourly.get("wind_direction_10m", [])
    gusts = hourly.get("wind_gusts_10m", [])

    rows = []
    for i, t in enumerate(times):
        speed = speeds[i] if i < len(speeds) else None
        rows.append({
            "observed_at": datetime.fromisoformat(t).replace(tzinfo=timezone.utc),
            "twd_deg": dirs[i] if i < len(dirs) else None,
            "tws_kts": round(speed * MS_TO_KTS, 1) if speed is not None else None,
            "gust_kts": round(gusts[i] * MS_TO_KTS, 1) if i < len(gusts) and gusts[i] is not None else None,
            "is_forecast": is_forecast,
        })
    return rows


def fetch_station(external_station_id: str) -> "list[dict]":
    """Forecast endpoint — rows are provisional (``is_forecast=True``): the
    reconciliation job (``services/wind_lookup.reconcile_forecasts``) later
    overwrites them with the archive's settled values."""
    lat, lng = _parse_latlng(external_station_id)
    hourly = _fetch_best_model(FORECAST_URL, lat, lng,
                               {"forecast_days": 3, "past_days": 1})
    return _rows_from_hourly(hourly, is_forecast=True)


def fetch_historical(external_station_id: str, start_date: str, end_date: str) -> "list[dict]":
    """Backfill past observations from Open-Meteo's reanalysis archive
    (``start_date``/``end_date`` as ``YYYY-MM-DD``). Used when a session
    predates the forecast endpoint's ``past_days`` window — see
    ``services/wind_lookup.backfill_historical`` — and by the reconciliation
    job to replace provisional forecast rows. Archive rows are never
    provisional (``is_forecast=False``), even for very recent dates (Open-
    Meteo serves ERA5T preliminary reanalysis there, already more settled
    than the forecast model)."""
    lat, lng = _parse_latlng(external_station_id)
    hourly = _fetch_best_model(ARCHIVE_URL, lat, lng,
                               {"start_date": start_date, "end_date": end_date})
    return _rows_from_hourly(hourly, is_forecast=False)
