"""Tack and gybe detection with per-maneuver performance metrics.

Detects maneuvers by finding rapid heading changes while the boat
is moving, then computes speed loss, recovery time, and other metrics.
"""

import math

import numpy as np

from .models import GpsPoint, ImuReading, Maneuver, ManeuverType


# Detection thresholds
MAX_MANEUVER_DURATION_SEC = 30  # max time for heading change
MIN_BOAT_SPEED_KTS = 1.5  # ignore turns while nearly stopped
SPEED_RECOVERY_THRESHOLD = 0.9  # 90% of entry speed
MAX_RECOVERY_WINDOW_SEC = 60
TURN_RATE_THRESHOLD = 3.0  # deg/sec to detect turn
TURN_WINDOW_EXTEND_SEC = 5  # extend window before/after rapid portion
MIN_MANEUVER_SPACING_SEC = 20  # minimum time between maneuvers to avoid duplicates
HEADING_SMOOTH_WINDOW = 5  # samples, circular moving average before detection
HOLD_WINDOW_SEC = 12  # min dwell time on a side for it to count as a real tack
# A genuine tack/gybe is a real rotation, not just a slow drift that happens
# to cross the wind-axis boundary the side-debounce logic tracks (e.g. a
# zero-duration/zero-change "maneuver" is a detection glitch, not a real
# one). Gybes have no dead zone the way tacking does — a boat already
# sailing deep can gybe with a fairly modest heading change — so this floor
# is only high enough to reject the degenerate cases, not to demand a wide
# rotation.
MIN_TACK_HEADING_CHANGE_DEG = 40
MIN_GYBE_HEADING_CHANGE_DEG = 20


def detect_maneuvers(
    gps: list[GpsPoint],
    imu: list[ImuReading] | None = None,
    twd_deg: float | None = None,
) -> list[Maneuver]:
    """Detect tacks and gybes from heading changes.

    A maneuver is a genuine tack-side change (port/starboard relative to the
    wind axis), not just any rapid heading change — a tactical heading wiggle
    or an aborted/failed maneuver that rounds back never really settles onto
    the new side, so neither should count. This is enforced structurally: the
    whole per-sample side sequence is first debounced (`_debounced_sides`),
    absorbing any side run shorter than `HOLD_WINDOW_SEC` into its
    predecessor, so every remaining transition is guaranteed to have *both* a
    settled "before" and a settled "after" side — not just checked one-sided
    after the fact. Only those transitions become maneuver candidates, each
    then refined to its precise start/end (where the heading actually starts/
    stops turning) for the duration/speed-loss metrics below. Without real
    wind data (`twd_deg`), falls back to a synthetic axis (the track's
    circular-mean heading) for the same side test, at reduced confidence.
    """
    if len(gps) < 20:
        return []

    # Use GPS course for heading - IMU heading often has mounting offset issues
    times = np.array([p.timestamp for p in gps])
    raw_headings = np.array([p.heading_deg for p in gps])
    # Smoothed heading drives candidate detection — plain GPS-course jitter
    # near head-to-wind/dead-downwind otherwise triggers spurious candidates.
    headings = _smooth_heading(raw_headings)

    # GPS speed series for speed loss calculation
    gps_times = np.array([p.timestamp for p in gps])
    gps_speeds = np.array([p.speed_kts for p in gps])
    gps_lats = np.array([p.lat for p in gps])
    gps_lons = np.array([p.lon for p in gps])

    axis_deg = twd_deg if twd_deg is not None else _circular_mean(raw_headings)

    # Window used only to refine each candidate's precise start/end once a
    # real transition has already been located (see WINDOW_SIZE usage below).
    WINDOW_SIZE = 25  # samples (seconds at 1Hz)

    sides = np.array([_tack_side(h, axis_deg) for h in headings])
    sides = _debounced_sides(sides, times, HOLD_WINDOW_SEC)
    transitions = np.where(np.diff(sides) != 0)[0]

    maneuvers = []
    last_maneuver_end = -999999

    for pivot in transitions:
        # Refine the actual turn boundaries around the debounced transition:
        # scan backward for where the rapid heading change begins, forward
        # for where it stabilizes on the new side (same rate-of-turn logic
        # as before, just anchored on a confirmed real transition).
        start_idx = pivot
        floor = max(5, pivot - WINDOW_SIZE)
        while start_idx > floor:
            local_change = abs(_angular_diff(headings[start_idx], headings[start_idx - 5]))
            if local_change < 10:
                break
            start_idx -= 1

        end_idx = pivot
        ceiling = min(len(headings) - 5, pivot + WINDOW_SIZE)
        while end_idx < ceiling:
            local_change = abs(_angular_diff(headings[end_idx + 5], headings[end_idx]))
            if local_change < 5:  # Heading stabilized
                break
            end_idx += 1

        t_start = times[start_idx]
        t_end = times[end_idx]
        duration = t_end - t_start

        if duration > MAX_MANEUVER_DURATION_SEC:
            continue
        if t_start < last_maneuver_end + MIN_MANEUVER_SPACING_SEC:
            continue

        heading_before = headings[start_idx]
        heading_after = headings[end_idx]
        heading_change = _angular_diff(heading_after, heading_before)

        # Speed metrics (interpolate GPS speed at maneuver boundaries)
        speed_before = float(np.interp(t_start, gps_times, gps_speeds))
        if speed_before < MIN_BOAT_SPEED_KTS:
            continue

        rel_before = _angular_diff(heading_before, axis_deg)
        rel_after = _angular_diff(heading_after, axis_deg)

        # Find minimum speed during maneuver
        mask = (gps_times >= t_start) & (gps_times <= t_end)
        if mask.sum() > 0:
            speed_min = float(gps_speeds[mask].min())
        else:
            speed_min = float(np.interp((t_start + t_end) / 2, gps_times, gps_speeds))

        # Find speed after and recovery time
        speed_after, recovery_time = _compute_recovery(
            gps_times, gps_speeds, t_end, speed_before
        )

        # Classify as tack or gybe
        maneuver_type = _classify_maneuver(rel_before, rel_after)

        min_change = (MIN_GYBE_HEADING_CHANGE_DEG if maneuver_type == ManeuverType.GYBE
                     else MIN_TACK_HEADING_CHANGE_DEG)
        if abs(heading_change) < min_change:
            continue

        # Heel during maneuver (from IMU)
        max_heel = None
        if imu:
            imu_times_arr = np.array([r.timestamp for r in imu])
            imu_heels = np.array([r.heel_deg for r in imu])
            mask_imu = (imu_times_arr >= t_start) & (imu_times_arr <= t_end)
            if mask_imu.sum() > 0:
                max_heel = float(np.max(np.abs(imu_heels[mask_imu])))

        # Start position
        start_lat = float(np.interp(t_start, gps_times, gps_lats))
        start_lon = float(np.interp(t_start, gps_times, gps_lons))

        maneuvers.append(Maneuver(
            maneuver_type=maneuver_type,
            start_time=t_start,
            end_time=t_end,
            duration_sec=round(duration, 1),
            speed_loss_kts=round(speed_before - speed_min, 2),
            speed_before_kts=round(speed_before, 2),
            speed_min_kts=round(speed_min, 2),
            speed_after_kts=round(speed_after, 2),
            recovery_time_sec=round(recovery_time, 1),
            heading_change_deg=round(heading_change, 1),
            max_heel_deg=round(max_heel, 1) if max_heel else None,
            start_lat=start_lat,
            start_lon=start_lon,
        ))
        last_maneuver_end = t_end

    return maneuvers


def _angular_diff(a: float | np.ndarray, b: float | np.ndarray) -> float | np.ndarray:
    """Signed angular difference a - b, result in [-180, 180]."""
    d = a - b
    if isinstance(d, np.ndarray):
        d = (d + 180) % 360 - 180
    else:
        d = (d + 180) % 360 - 180
    return d


def _circular_mean(angles_deg: np.ndarray) -> float:
    """Mean of a set of angles via their unit vectors — a plain arithmetic
    mean breaks near the 0°/360° wraparound."""
    rad = np.radians(angles_deg)
    return float(np.degrees(np.arctan2(np.mean(np.sin(rad)), np.mean(np.cos(rad)))) % 360)


def _smooth_heading(headings_deg: np.ndarray, window: int = HEADING_SMOOTH_WINDOW) -> np.ndarray:
    """Centered circular moving average (via unit vectors, to avoid
    wraparound artifacts a plain arithmetic mean would introduce) — reduces
    compass/GPS-course jitter that would otherwise trigger spurious
    rate-of-turn candidates in the sliding-window scan."""
    if len(headings_deg) < window:
        return headings_deg
    rad = np.radians(headings_deg)
    kernel = np.ones(window) / window
    pad_before, pad_after = window // 2, window - 1 - window // 2
    cos_s = np.convolve(np.pad(np.cos(rad), (pad_before, pad_after), mode="edge"), kernel, mode="valid")
    sin_s = np.convolve(np.pad(np.sin(rad), (pad_before, pad_after), mode="edge"), kernel, mode="valid")
    return np.degrees(np.arctan2(sin_s, cos_s)) % 360


def _tack_side(heading_deg: float, axis_deg: float) -> int:
    """+1 = starboard tack (wind from the right of the axis), -1 = port."""
    return 1 if _angular_diff(heading_deg, axis_deg) > 0 else -1


def _debounced_sides(sides: np.ndarray, times: np.ndarray, min_run_sec: float) -> np.ndarray:
    """Minimum-dwell-time filter on a per-sample tack-side sequence: any run
    shorter than `min_run_sec` is absorbed into the run before it. This is
    what actually distinguishes a genuine maneuver from a brief wiggle or an
    aborted attempt that rounds back — a transition only survives if *both*
    neighboring sides were themselves genuinely settled, not just the side
    after it (checking one side only would let an aborted maneuver's rebound
    read as a fresh, valid transition). Iterates to convergence since
    absorbing one short run can join two longer runs that then need
    re-checking (rare in practice, bounded for safety)."""
    sides = sides.copy()
    n = len(sides)
    for _ in range(5):
        changed = False
        i = 0
        while i < n:
            j = i
            while j < n and sides[j] == sides[i]:
                j += 1
            run_sec = times[min(j, n - 1)] - times[i]
            if run_sec < min_run_sec and 0 < i < n:
                sides[i:j] = sides[i - 1]
                changed = True
            i = j
        if not changed:
            break
    return sides


def _classify_maneuver(rel_before: float, rel_after: float) -> ManeuverType:
    """Tack = the bow crosses head-to-wind (both headings within 90° of the
    wind axis); gybe = the stern crosses (both beyond 90°). Called only after
    a real side change has already been confirmed by the caller."""
    avg_abs_rel = (abs(rel_before) + abs(rel_after)) / 2
    return ManeuverType.TACK if avg_abs_rel < 90 else ManeuverType.GYBE


def _compute_recovery(
    gps_times: np.ndarray,
    gps_speeds: np.ndarray,
    maneuver_end: float,
    speed_before: float,
) -> tuple[float, float]:
    """Find speed after maneuver and time to recover to 90% entry speed."""
    target = speed_before * SPEED_RECOVERY_THRESHOLD
    mask = gps_times > maneuver_end
    future_times = gps_times[mask]
    future_speeds = gps_speeds[mask]

    if len(future_times) == 0:
        return speed_before, 0.0

    # Speed 5 seconds after maneuver
    t_after = maneuver_end + 5.0
    speed_after = float(np.interp(t_after, gps_times, gps_speeds))

    # Recovery time
    window_mask = (future_times - maneuver_end) < MAX_RECOVERY_WINDOW_SEC
    window_speeds = future_speeds[window_mask]
    window_times = future_times[window_mask]

    recovered = window_speeds >= target
    if recovered.any():
        first_idx = np.argmax(recovered)
        recovery_time = window_times[first_idx] - maneuver_end
    else:
        recovery_time = MAX_RECOVERY_WINDOW_SEC

    return speed_after, recovery_time


def maneuver_summary(maneuvers: list[Maneuver]) -> dict:
    """Compute summary statistics for all maneuvers."""
    tacks = [m for m in maneuvers if m.maneuver_type == ManeuverType.TACK]
    gybes = [m for m in maneuvers if m.maneuver_type == ManeuverType.GYBE]

    def _stats(group: list[Maneuver]) -> dict:
        if not group:
            return {"count": 0}
        speeds_lost = [m.speed_loss_kts for m in group]
        recovery_times = [m.recovery_time_sec for m in group]
        durations = [m.duration_sec for m in group]
        return {
            "count": len(group),
            "avg_speed_loss_kts": round(np.mean(speeds_lost), 2),
            "avg_recovery_sec": round(np.mean(recovery_times), 1),
            "avg_duration_sec": round(np.mean(durations), 1),
            "best_speed_loss_kts": round(min(speeds_lost), 2),
            "worst_speed_loss_kts": round(max(speeds_lost), 2),
        }

    return {
        "tacks": _stats(tacks),
        "gybes": _stats(gybes),
        "total": len(maneuvers),
    }
