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
FETCH_TIMEOUT_S = 15

MS_TO_KTS = 1.94384


def fetch_station(external_station_id: str) -> "list[dict]":
    try:
        lat_s, lng_s = external_station_id.split(",")
        lat, lng = float(lat_s), float(lng_s)
    except ValueError:
        raise ValueError(
            f"open_meteo external_station_id must be 'lat,lng', got {external_station_id!r}"
        )

    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lng,
            "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "wind_speed_unit": "ms",
            "forecast_days": 3,
            "past_days": 1,
        },
        timeout=FETCH_TIMEOUT_S,
    )
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})
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
        })
    return rows
