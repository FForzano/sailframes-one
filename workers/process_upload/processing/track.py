"""Pluggable, JOINT estimation of a session's position (lat/lon) and motion
(speed/heading) from raw records — two distinct output series (not fused
into one blob, since they're conceptually different quantities you may want
to persist/inspect separately), but computed together in one pass, not by
two independently-invoked strategies. That's deliberate: a real joint
algorithm (e.g. a Kalman filter fusing GPS fixes with heading/speed into one
state estimate) can't cleanly split "estimate my position" from "estimate my
velocity" into two separately-callable steps without losing the coupling
between them — position and motion here are two views of the same
underlying state, not two unrelated computations that happen to share input.

This is a processing seam, not a parsing one: it takes records already
extracted from whatever source format (GPX via ``services/gpx.py``, device
CSV via ``handler.py``) and normalized into the on-disk ``gps.json`` dict
shape — it does not touch raw file parsing.

Add a strategy: a function ``(records) -> (position, motion)`` with
``position: list[{timestamp, lat, lon, fix_quality}]`` and
``motion: list[{timestamp, speed_kts, heading_deg}]``; register it in
``STRATEGIES``, swap ``ACTIVE_STRATEGY`` to experiment (constant, not
env-configurable — change it and rebuild the worker image).
"""

import math
from datetime import datetime
from typing import Callable

import numpy as np

from .kalman_filter import ConstantVelocity2D, KalmanFilter, linear_measurement
from .models import GpsPoint

TrackEstimator = Callable[["list[dict]"], "tuple[list[dict], list[dict]]"]


def to_timestamp(t) -> float:
    """Convert ISO string or datetime to Unix timestamp."""
    if isinstance(t, (int, float)):
        return float(t)
    if isinstance(t, str):
        t = t.replace("Z", "+00:00")
        return datetime.fromisoformat(t).timestamp()
    if isinstance(t, datetime):
        return t.timestamp()
    return 0.0


def parse_as_is(records: "list[dict]") -> "tuple[list[dict], list[dict]]":
    """Today's behavior: trust every fix verbatim, tolerant of a few
    field-name variants across sources (GPX vs. E1 vs. S1 CSV) — no
    filtering, smoothing, or fusion of any kind. Position and motion are
    trivial projections of the same record here; a real joint algorithm
    would derive them together from shared internal state instead."""
    position, motion = [], []
    for r in records:
        if "timestamp" not in r and "t" not in r:
            continue
        t = to_timestamp(r.get("timestamp", r.get("t", "")))
        position.append({
            "timestamp": t,
            "lat": r.get("lat", r.get("latitude", 0)),
            "lon": r.get("lon", r.get("longitude", 0)),
            "fix_quality": r.get("fix_quality", r.get("fix", 0)),
        })
        motion.append({
            "timestamp": t,
            "speed_kts": r.get("speed_kts", r.get("speed_kn", r.get("speed", 0))),
            "heading_deg": r.get("heading_deg", r.get("course", r.get("heading", 0))),
        })
    return position, motion


def _local_enu_projection(lat0_deg: float):
    """Equirectangular tangent-plane projection around ``lat0_deg``, good
    enough for the metre-scale, session-length tracks this pipeline deals
    with (do not reuse for anything spanning tens of km or crossing a
    pole/antimeridian — a real geodesic projection would be needed there).
    Returns (to_xy, to_lat_lon)."""
    lat0 = math.radians(lat0_deg)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(lat0)

    def to_xy(lat: float, lon: float) -> tuple[float, float]:
        return (lon * m_per_deg_lon, lat * m_per_deg_lat)

    def to_lat_lon(x: float, y: float) -> tuple[float, float]:
        return (y / m_per_deg_lat, x / m_per_deg_lon)

    return to_xy, to_lat_lon


def kalman_cv(records: "list[dict]") -> "tuple[list[dict], list[dict]]":
    """Joint position/velocity estimate via a ``KalmanFilter`` over a
    ``ConstantVelocity2D`` motion model (see ``kalman_filter.py``), in a
    local ENU (metres) tangent plane.

    State ``[x, y, vx, vy]``. Each GPS sample becomes a single linear
    ``Measurement`` observing all four components: position directly, and
    velocity as ``vx/vy`` decomposed from the speed/course fix (trig of a
    *measurement*, not of the state — so ``H`` is constant, no Jacobian).

    Everything domain-specific lives here — the ENU projection and the
    knots/heading ↔ velocity-vector conversion; all the filter algebra is
    in ``kalman_filter.py``. A future sensor (IMU heading, UWB range to a
    buoy) is added the same way: another producer of ``Measurement``s
    merged into this loop's timeline, not a change to this function's
    existing GPS handling. A signal that must be fused *nonlinearly* (a raw
    compass angle, a UWB distance) would build a ``Measurement`` with its
    own ``predict_z``/``jacobian`` instead of ``linear_measurement`` — the
    filter's EKF update already handles it; only a signal warranting new
    *state* components (an explicit heading/yaw-rate) would call for a new
    ``MotionModel`` subclass.

    Tune ``Q_*``/``R_*`` against real tracks before ever making this the
    active strategy — these starting values are a plausible order of
    magnitude for a GPS boat track, not a calibrated fit.
    """
    parsed = sorted(
        (
            (to_timestamp(r.get("timestamp", r.get("t", ""))), r)
            for r in records
            if "timestamp" in r or "t" in r
        ),
        key=lambda pair: pair[0],
    )
    if not parsed:
        return [], []

    lat0 = parsed[0][1].get("lat", parsed[0][1].get("latitude", 0)) or 0.0
    to_xy, to_lat_lon = _local_enu_projection(lat0)

    # Process noise (accel-driven random walk on velocity) and measurement
    # noise (GPS position ~metres, GPS speed/course fix ~kts/degrees translated
    # into an ENU velocity uncertainty) — starting points, expect to tune.
    Q_ACCEL_VAR = 0.25       # (m/s^2)^2 — how much the boat's velocity can change per second
    R_POS_VAR = 25.0         # m^2 — GPS fix position noise
    R_VEL_VAR = 0.5          # (m/s)^2 — GPS-derived velocity noise

    x0, y0 = to_xy(lat0, parsed[0][1].get("lon", parsed[0][1].get("longitude", 0)) or 0.0)
    kf = KalmanFilter(
        model=ConstantVelocity2D(accel_variance=Q_ACCEL_VAR),
        initial_state=np.array([x0, y0, 0.0, 0.0], dtype=float),
        initial_covariance=np.diag([R_POS_VAR, R_POS_VAR, R_VEL_VAR, R_VEL_VAR]),
    )
    # GPS observes all four state components; its measurement model is
    # constant (H = identity, R = fixed sensor noise). Per-sample fix_quality
    # could scale R here in the future — the field is read but not yet used.
    H_gps = np.eye(4)
    R_gps = np.diag([R_POS_VAR, R_POS_VAR, R_VEL_VAR, R_VEL_VAR])

    position, motion = [], []
    prev_t = parsed[0][0]

    for t, r in parsed:
        dt = t - prev_t
        prev_t = t

        # -- measurement: GPS fix (position) + GPS-derived velocity --
        lat = r.get("lat", r.get("latitude", 0)) or 0.0
        lon = r.get("lon", r.get("longitude", 0)) or 0.0
        mx, my = to_xy(lat, lon)

        speed_kts = r.get("speed_kts", r.get("speed_kn", r.get("speed", 0))) or 0.0
        heading_deg = r.get("heading_deg", r.get("course", r.get("heading", 0))) or 0.0
        speed_mps = speed_kts * 0.514444
        heading_rad = math.radians(heading_deg)
        mvx = speed_mps * math.sin(heading_rad)  # east component (heading 0 = north)
        mvy = speed_mps * math.cos(heading_rad)  # north component

        kf.predict(dt)
        state = kf.update(linear_measurement(t, [mx, my, mvx, mvy], H_gps, R_gps))

        lat_est, lon_est = to_lat_lon(state[0], state[1])
        vx, vy = state[2], state[3]
        speed_est_kts = math.hypot(vx, vy) / 0.514444
        heading_est_deg = (math.degrees(math.atan2(vx, vy)) + 360) % 360

        position.append({
            "timestamp": t,
            "lat": lat_est,
            "lon": lon_est,
            "fix_quality": r.get("fix_quality", r.get("fix", 0)),
        })
        motion.append({
            "timestamp": t,
            "speed_kts": speed_est_kts,
            "heading_deg": heading_est_deg,
        })

    return position, motion


STRATEGIES: "dict[str, TrackEstimator]" = {
    "as_is": parse_as_is,
    "kalman_cv": kalman_cv,
}

# Change this (and rebuild the worker image) to switch strategies.
ACTIVE_STRATEGY = "kalman_cv"


def estimate(records: "list[dict]") -> "tuple[list[dict], list[dict]]":
    return STRATEGIES[ACTIVE_STRATEGY](records)


def merge(position: "list[dict]", motion: "list[dict]") -> "list[GpsPoint]":
    """Recombine the two series into the ``GpsPoint`` shape the rest of the
    pipeline (maneuvers/legs/wind/vmg/polar) already consumes, unchanged.

    Paired by index when both series have the same length — true for every
    strategy that (like ``parse_as_is`` above) derives them from one pass
    over the same records in the same order, and the only way to keep two
    points that happen to share a timestamp (real GPS data has these) from
    silently collapsing onto the same motion values. Falls back to an
    exact-timestamp lookup for a future estimator that samples position and
    motion at genuinely different rates (duplicate timestamps there would
    still collapse to the last one seen — a real interpolation, not this
    plain zip, would be needed to do better)."""
    if len(position) == len(motion):
        return [GpsPoint(
            timestamp=p["timestamp"],
            lat=p["lat"],
            lon=p["lon"],
            speed_kts=m["speed_kts"],
            heading_deg=m["heading_deg"],
            fix_quality=p.get("fix_quality", 0),
        ) for p, m in zip(position, motion)]

    motion_by_t = {m["timestamp"]: m for m in motion}
    points = []
    for p in position:
        m = motion_by_t.get(p["timestamp"])
        if m is None:
            continue
        points.append(GpsPoint(
            timestamp=p["timestamp"],
            lat=p["lat"],
            lon=p["lon"],
            speed_kts=m["speed_kts"],
            heading_deg=m["heading_deg"],
            fix_quality=p.get("fix_quality", 0),
        ))
    return points
