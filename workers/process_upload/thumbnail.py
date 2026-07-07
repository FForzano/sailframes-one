"""Small track-preview PNG — rendered once by the worker from ``gps.json`` and
reused as-is by the sessions list (frontend/src/pages/diario/SessionsPage.tsx)
instead of re-rendering the track on every page load.
"""

from io import BytesIO
from math import cos, radians

from PIL import Image, ImageDraw

THUMB_SIZE = (160, 120)
THUMB_PADDING = 10
TRACK_COLOR = (47, 155, 224, 255)  # --sf-primary (frontend/src/styles/global.css)
MAX_POINTS = 500  # plenty of detail at ~150px; keeps rendering cheap


def render_track_thumbnail(gps_points: list) -> "bytes | None":
    """`gps_points` are ``gps.json`` records (need only ``lat``/``lon``).
    Flat equirectangular projection (cos-latitude longitude correction) —
    good enough at the few-km scale of a single session, no need for a real
    map projection. Returns None if there aren't enough points for a line."""
    coords = [
        (p["lat"], p["lon"]) for p in gps_points
        if p.get("lat") is not None and p.get("lon") is not None
    ]
    if len(coords) < 2:
        return None

    step = max(1, len(coords) // MAX_POINTS)
    coords = coords[::step]

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lon_scale = cos(radians((min_lat + max_lat) / 2)) or 1.0

    w, h = THUMB_SIZE
    pad = THUMB_PADDING
    lat_span = max(max_lat - min_lat, 1e-9)
    lon_span = max((max_lon - min_lon) * lon_scale, 1e-9)
    scale = min((w - 2 * pad) / lon_span, (h - 2 * pad) / lat_span)

    drawn_w = lon_span * scale
    drawn_h = lat_span * scale
    off_x = pad + ((w - 2 * pad) - drawn_w) / 2
    off_y = pad + ((h - 2 * pad) - drawn_h) / 2

    def project(lat: float, lon: float) -> tuple:
        x = off_x + (lon - min_lon) * lon_scale * scale
        y = h - off_y - (lat - min_lat) * scale  # flip: image Y grows downward
        return (x, y)

    img = Image.new("RGBA", THUMB_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line([project(lat, lon) for lat, lon in coords], fill=TRACK_COLOR, width=2, joint="curve")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
