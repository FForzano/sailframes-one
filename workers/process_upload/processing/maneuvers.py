"""Maneuver detection — two-stage pipeline.

Stage 1 (this module): ``_detect_candidates`` segments the track into
roughly-constant-heading legs and emits a candidate for every turn between them
(``_turn_pivots``) — a purely geometric, WIND-AGNOSTIC step that does not decide
what kind of turn it is. It refines each turn's boundaries, computes the
type-independent performance metrics, and extracts a configurable statistical
feature vector (see ``maneuver_features``). Stage 2
(``maneuver_classification``): a pluggable classifier scores each candidate and
maps it to a ``ManeuverType`` — or to ``None`` (false alarm) so the candidate is
dropped. The wind axis is resolved here only to *describe* candidates
(``rel_before``/``rel_after`` for the classifier), never to find them.

``detect_maneuvers`` is the public entry point that composes the two stages; the
active ``probabilistic`` classifier owns rejection and the
tack/gybe/course_change labelling.
"""

import numpy as np

from .angles import angular_diff as _angular_diff
from .angles import circular_mean as _circular_mean
from .maneuver_classification import classify_maneuver
from .maneuver_features import FeatureContext, extract_features
from .models import GpsPoint, ImuReading, Maneuver, ManeuverCandidate, ManeuverType


# Detection thresholds
MAX_MANEUVER_DURATION_SEC = 30  # max time for heading change
MIN_BOAT_SPEED_KTS = 1.5  # ignore turns while nearly stopped
SPEED_RECOVERY_THRESHOLD = 0.9  # 90% of entry speed
MAX_RECOVERY_WINDOW_SEC = 60
TURN_RATE_THRESHOLD = 2.0  # deg/sec — a sample counts as "turning" above this.
# Matches the boundary-refine scan's own "turn begins" bar (10 deg / 5 samples
# below) so a slow, wide mark rounding (e.g. bolina->lasco over 20-30s, only
# ~2-3 deg/s) still crosses it — a real rounding is a sustained turn, not a
# snap one, so this must not be tuned to tack/gybe speeds alone.
TURN_WINDOW_EXTEND_SEC = 5  # bridge turning runs split by a brief rate dip
MIN_TURN_CANDIDATE_DEG = 15  # net heading change for a turn to be a candidate
MIN_MANEUVER_SPACING_SEC = 20  # minimum time between maneuvers to avoid duplicates
# backend/services/maneuver_reconciliation.py::OVERLAP_TOLERANCE_SEC (15s)
# must stay strictly below this — see that module's docstring.
HEADING_SMOOTH_WINDOW = 5  # samples, circular moving average before detection
# Per-type minimum heading change (fallback floor). Both production paths call
# _finalize with enforce_min_heading_change=False — automatic detection leaves
# rejection to the probabilistic classifier's confidence score, manual add to
# the user's judgement — so this floor is the documented minimum sensible
# rotation, exercised directly only by unit tests. A gybe needs less than a
# tack: a boat already sailing deep can gybe with a fairly modest rotation.
MIN_TACK_HEADING_CHANGE_DEG = 40
MIN_GYBE_HEADING_CHANGE_DEG = 20


def detect_maneuvers(
    gps: list[GpsPoint],
    imu: list[ImuReading] | None = None,
    twd_deg: float | None = None,
    true_wind: list[dict] | None = None,
) -> list[Maneuver]:
    """Detect tacks, gybes and course changes from heading changes (public
    entry point).

    Composes the two stages: Stage 1 (``_detect_candidates``) produces the
    turn candidates with their metrics + features; Stage 2 (``classify_maneuver``)
    scores each one — labelling it tack/gybe/course_change or rejecting it as a
    false alarm. The inter-maneuver spacing gate stays HERE, interleaved with
    classification and only advancing ``last_maneuver_end`` on a real append.

    ``true_wind`` (per-point series) only feeds the TWA/VMG-based *features*;
    it does not affect which maneuvers are detected or how they're classified,
    so the result is identical whether or not it is provided.
    """
    candidates = _detect_candidates(gps, imu, twd_deg, true_wind)

    maneuvers: list[Maneuver] = []
    last_maneuver_end = -999999
    for cand in candidates:
        # Inter-maneuver spacing: same semantics as before — measured against
        # the end of the last ACCEPTED maneuver, so candidates dropped below
        # never reset the baseline.
        if cand.start_time < last_maneuver_end + MIN_MANEUVER_SPACING_SEC:
            continue

        maneuver_type = classify_maneuver(cand)
        if maneuver_type is None:
            continue  # false alarm — not a real maneuver

        # LABEL-COLLECTION HOOK (future): here is where a "corrected label"
        # from the user, or a training-data sink, would attach — cand.features
        # is fully populated at this point.

        # The classifier's confidence score already owns rejection, so the hard
        # per-type min-heading gate is not applied on the automatic path (it
        # would only duplicate/second-guess the score) — _finalize just builds
        # the Maneuver here. enforce=False never returns None.
        maneuver = _finalize(cand, maneuver_type, enforce_min_heading_change=False)

        maneuvers.append(maneuver)
        last_maneuver_end = cand.end_time

    return maneuvers


def _detect_candidates(
    gps: list[GpsPoint],
    imu: list[ImuReading] | None,
    twd_deg: float | None,
    true_wind: list[dict] | None = None,
) -> list[ManeuverCandidate]:
    """Stage 1: segment the track into constant-heading legs and emit a
    candidate for every turn between them — wind-agnostic.

    Candidate GENERATION knows nothing about the wind: ``_turn_pivots`` finds
    every sustained heading change (a turn between two roughly-steady legs),
    and each such turn is a candidate. Deciding whether a turn is a tack, a
    gybe, a same-tack course change, or a false alarm is entirely Stage 2's job
    (`maneuver_classification`), so there is no duplicated "what kind of turn"
    logic here. The wind axis is still resolved (real ``twd_deg`` when
    available, else the track's circular-mean heading as a synthetic axis) and
    passed to ``_candidate_from_window`` only so the candidate carries
    ``rel_before``/``rel_after`` for the classifier.

    Each turn's boundaries are refined to where the heading actually
    starts/stops turning, then its type-independent metrics + feature vector
    are computed. Applies only the classification-INDEPENDENT gates (duration,
    entry speed). The spacing gate is applied by the caller
    (`detect_maneuvers`), interleaved with classification.
    """
    if len(gps) < 20:
        return []

    times, raw_headings, headings, gps_speeds, gps_lats, gps_lons = _detection_arrays(gps)
    # Resolved to DESCRIBE candidates (rel_before/rel_after), never to find them.
    axis_deg, had_wind_axis = resolve_wind_axis(raw_headings, twd_deg)

    # Window used only to refine each candidate's precise start/end once a turn
    # pivot has already been located (see WINDOW_SIZE usage below).
    WINDOW_SIZE = 25  # samples (seconds at 1Hz)

    candidates: list[ManeuverCandidate] = []

    for pivot in _turn_pivots(times, headings):
        # Refine the actual turn boundaries around the pivot: scan backward for
        # where the rapid heading change begins, forward for where it
        # stabilizes onto the new heading. This boundary search is specific to
        # "found a turn, where exactly does it start/end" — a manual maneuver
        # skips it entirely since the user already gives exact boundaries (see
        # compute_manual_maneuver).
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

        t_start, t_end = times[start_idx], times[end_idx]
        if t_end - t_start > MAX_MANEUVER_DURATION_SEC:
            continue

        cand = _candidate_from_window(
            gps, imu, true_wind, axis_deg, had_wind_axis,
            times, headings, gps_speeds, gps_lats, gps_lons,
            t_start, t_end,
        )
        if cand is None:
            continue
        candidates.append(cand)

    return candidates


def _detection_arrays(gps: list[GpsPoint]):
    """Series shared by every use of the maneuver pipeline (both automatic
    detection and a manual maneuver's on-demand stat computation) — GPS
    course, not IMU heading (mounting offset issues), drives everything.
    ``headings`` is smoothed (plain GPS-course jitter near head-to-wind/
    dead-downwind otherwise triggers spurious candidates); ``raw_headings``
    is kept separately for the wind-axis fallback, which wants the track's
    real shape, not the smoothed one."""
    times = np.array([p.timestamp for p in gps])
    raw_headings = np.array([p.heading_deg for p in gps])
    headings = _smooth_heading(raw_headings)
    gps_speeds = np.array([p.speed_kts for p in gps])
    gps_lats = np.array([p.lat for p in gps])
    gps_lons = np.array([p.lon for p in gps])
    return times, raw_headings, headings, gps_speeds, gps_lats, gps_lons


def resolve_wind_axis(raw_headings: np.ndarray, twd_deg: float | None) -> "tuple[float, bool]":
    """Real wind axis when available, else a synthetic one (the track's
    circular-mean heading) at reduced confidence — same fallback
    ``_detect_candidates`` always used, factored out so the manual-maneuver
    path resolves the axis identically."""
    had_wind_axis = twd_deg is not None
    axis_deg = twd_deg if had_wind_axis else _circular_mean(raw_headings)
    return axis_deg, had_wind_axis


def _candidate_from_window(
    gps: list[GpsPoint],
    imu: list[ImuReading] | None,
    true_wind: list[dict] | None,
    axis_deg: float,
    had_wind_axis: bool,
    times: np.ndarray,
    headings: np.ndarray,
    gps_speeds: np.ndarray,
    gps_lats: np.ndarray,
    gps_lons: np.ndarray,
    t_start: float,
    t_end: float,
) -> "ManeuverCandidate | None":
    """Compute a candidate's type-independent metrics + feature vector for a
    given ``[t_start, t_end]`` window — the "given boundaries, describe this
    maneuver" half of what used to be inlined in ``_detect_candidates``'s
    per-transition loop. Boundary-finding stays the caller's job (either
    ``_detect_candidates``'s rate-of-turn scan, or a user's explicit click
    window — see ``compute_manual_maneuver``), so both paths get identical
    stats/features for the same boundaries. Returns ``None`` if the boat was
    nearly stopped at the start (same gate ``_detect_candidates`` always
    applied) — a maneuver's speed-loss stats are meaningless below that."""
    start_idx = int(np.searchsorted(times, t_start))
    end_idx = min(int(np.searchsorted(times, t_end)), len(times) - 1)

    heading_before = float(headings[start_idx])
    heading_after = float(headings[end_idx])
    heading_change = _angular_diff(heading_after, heading_before)

    # Speed metrics (interpolate GPS speed at maneuver boundaries)
    speed_before = float(np.interp(t_start, times, gps_speeds))
    if speed_before < MIN_BOAT_SPEED_KTS:
        return None

    rel_before = _angular_diff(heading_before, axis_deg)
    rel_after = _angular_diff(heading_after, axis_deg)

    # Find minimum speed during maneuver
    mask = (times >= t_start) & (times <= t_end)
    if mask.sum() > 0:
        speed_min = float(gps_speeds[mask].min())
    else:
        speed_min = float(np.interp((t_start + t_end) / 2, times, gps_speeds))

    # Find speed after and recovery time
    speed_after, recovery_time = _compute_recovery(times, gps_speeds, t_end, speed_before)

    # Heel during maneuver (from IMU)
    max_heel = None
    if imu:
        imu_times_arr = np.array([r.timestamp for r in imu])
        imu_heels = np.array([r.heel_deg for r in imu])
        mask_imu = (imu_times_arr >= t_start) & (imu_times_arr <= t_end)
        if mask_imu.sum() > 0:
            max_heel = float(np.max(np.abs(imu_heels[mask_imu])))

    # Start position
    start_lat = float(np.interp(t_start, times, gps_lats))
    start_lon = float(np.interp(t_start, times, gps_lons))

    ctx = FeatureContext(
        gps=gps,
        imu=imu,
        true_wind=true_wind,
        axis_deg=float(axis_deg),
        had_wind_axis=had_wind_axis,
        t_start=float(t_start),
        t_end=float(t_end),
        heading_before=heading_before,
        heading_after=heading_after,
        speed_before_kts=speed_before,
        speed_min_kts=speed_min,
        speed_after_kts=speed_after,
        recovery_time_sec=recovery_time,
        rel_before=float(rel_before),
        rel_after=float(rel_after),
        max_heel_deg=max_heel,
    )

    return ManeuverCandidate(
        start_time=t_start,
        end_time=t_end,
        duration_sec=t_end - t_start,
        heading_change_deg=heading_change,
        speed_before_kts=speed_before,
        speed_min_kts=speed_min,
        speed_after_kts=speed_after,
        recovery_time_sec=recovery_time,
        start_lat=start_lat,
        start_lon=start_lon,
        features=extract_features(ctx),
    )


def compute_manual_maneuver(
    gps: list[GpsPoint],
    imu: list[ImuReading] | None,
    twd_deg: float | None,
    true_wind: list[dict] | None,
    t_start: float,
    t_end: float,
    maneuver_type: ManeuverType,
) -> Maneuver:
    """Stats/features for a user-specified maneuver window — the manual-add
    counterpart to ``_detect_candidates``/``_finalize``, reusing the exact
    same math via ``_candidate_from_window`` instead of duplicating it (see
    ``routers/sessions.py::add_maneuver`` for the caller, via a worker
    round-trip). Skips ``_detect_candidates``'s transition-scan entirely
    (the user already gives exact boundaries) and bypasses ``_finalize``'s
    per-type minimum-heading-change gate — a user explicitly placing a
    maneuver overrides that heuristic; it exists to filter out the
    algorithm's own noise, not a human's judgment.

    Raises ``ValueError`` if the window isn't a valid maneuver window (boat
    nearly stopped at the start) — the caller should surface this as an
    error, not silently drop the request the way automatic detection does.
    """
    times, _raw_headings, headings, gps_speeds, gps_lats, gps_lons = _detection_arrays(gps)
    axis_deg, had_wind_axis = resolve_wind_axis(_raw_headings, twd_deg)
    cand = _candidate_from_window(
        gps, imu, true_wind, axis_deg, had_wind_axis,
        times, headings, gps_speeds, gps_lats, gps_lons,
        t_start, t_end,
    )
    if cand is None:
        raise ValueError(
            f"Cannot compute a maneuver for [{t_start}, {t_end}]: "
            f"boat speed at t_start is below {MIN_BOAT_SPEED_KTS}kts."
        )
    maneuver = _finalize(cand, maneuver_type, enforce_min_heading_change=False)
    assert maneuver is not None  # enforce_min_heading_change=False never returns None
    return maneuver


def _finalize(
    cand: ManeuverCandidate,
    maneuver_type: ManeuverType,
    enforce_min_heading_change: bool = True,
) -> Maneuver | None:
    """Apply the per-type minimum-heading-change gate and build the final
    ``Maneuver``. Returns ``None`` (the old ``continue``) when the heading
    change is below the type's floor. Rounding matches the previous inline
    construction exactly; ``cand.features`` (which includes ``max_heel_deg`` —
    see ``maneuver_features._max_heel_deg``) is carried onto the maneuver for
    persistence.

    ``enforce_min_heading_change=False`` (used only by
    ``compute_manual_maneuver``) skips the gate entirely — a user placing a
    maneuver by hand overrides the heuristic that exists to filter the
    algorithm's own false positives, not a human's judgment."""
    min_change = (MIN_GYBE_HEADING_CHANGE_DEG
                  if maneuver_type in (ManeuverType.GYBE, ManeuverType.COURSE_CHANGE)
                  else MIN_TACK_HEADING_CHANGE_DEG)
    if enforce_min_heading_change and abs(cand.heading_change_deg) < min_change:
        return None

    return Maneuver(
        maneuver_type=maneuver_type,
        start_time=cand.start_time,
        end_time=cand.end_time,
        duration_sec=round(cand.duration_sec, 1),
        speed_loss_kts=round(cand.speed_before_kts - cand.speed_min_kts, 2),
        speed_before_kts=round(cand.speed_before_kts, 2),
        speed_min_kts=round(cand.speed_min_kts, 2),
        speed_after_kts=round(cand.speed_after_kts, 2),
        recovery_time_sec=round(cand.recovery_time_sec, 1),
        heading_change_deg=round(cand.heading_change_deg, 1),
        start_lat=cand.start_lat,
        start_lon=cand.start_lon,
        features=cand.features,
    )


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


def _close_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """Fill interior ``False`` runs no longer than ``max_gap`` that sit between
    two ``True`` runs — used to bridge a brief sub-threshold dip in turn rate
    in the middle of a single rotation, so one physical turn stays one run."""
    out = mask.copy()
    n = len(out)
    i = 0
    while i < n:
        if out[i]:
            i += 1
            continue
        j = i
        while j < n and not out[j]:
            j += 1
        if 0 < i and j < n and (j - i) <= max_gap:
            out[i:j] = True
        i = j
    return out


def _turn_pivots(times: np.ndarray, headings: np.ndarray) -> list[int]:
    """Wind-agnostic turn detection: one pivot index per sustained heading
    change, so Stage 1 just segments the track into roughly-constant-heading
    legs and leaves classification to Stage 2.

    A sample is "turning" when the smoothed heading changes faster than
    ``TURN_RATE_THRESHOLD`` over a short look-ahead; contiguous turning samples
    (bridging brief sub-threshold dips within one rotation, up to
    ``TURN_WINDOW_EXTEND_SEC``) form a turn, whose pivot is the sample of peak
    turn rate. Turns whose net heading change stays below
    ``MIN_TURN_CANDIDATE_DEG`` are dropped as jitter; a turn-and-back wiggle
    nets ~0 change here (and is rejected downstream anyway, since its refined
    window settles back on the original heading)."""
    n = len(headings)
    step = HEADING_SMOOTH_WINDOW  # look-ahead, matches the boundary-refine scan
    rate = np.zeros(n)
    for i in range(n - step):
        dt = times[i + step] - times[i]
        if dt > 0:
            rate[i] = _angular_diff(headings[i + step], headings[i]) / dt

    turning = np.abs(rate) > TURN_RATE_THRESHOLD
    turning = _close_gaps(turning, max_gap=int(round(TURN_WINDOW_EXTEND_SEC)))

    pivots: list[int] = []
    i = 0
    while i < n:
        if not turning[i]:
            i += 1
            continue
        j = i
        while j < n and turning[j]:
            j += 1
        net = abs(_angular_diff(headings[j - 1], headings[i]))
        if net >= MIN_TURN_CANDIDATE_DEG:
            pivots.append(i + int(np.argmax(np.abs(rate[i:j]))))
        i = j
    return pivots


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
    """Compute summary statistics for all maneuvers.

    ``course_changes`` is emitted for completeness (the third class); with the
    active geometric classifier no maneuver is labelled ``course_change``, so
    it stays at ``{"count": 0}`` today.
    """
    tacks = [m for m in maneuvers if m.maneuver_type == ManeuverType.TACK]
    gybes = [m for m in maneuvers if m.maneuver_type == ManeuverType.GYBE]
    course_changes = [m for m in maneuvers if m.maneuver_type == ManeuverType.COURSE_CHANGE]

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
        "course_changes": _stats(course_changes),
        "total": len(maneuvers),
    }
