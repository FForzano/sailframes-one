"""Fase 3 — the GPS tack-axis contributor: gating (only genuine beats/runs),
180° resolution against the speed-bearing sources, and its low-weight,
direction-only effect on the fused series."""

import pytest

from processing.models import GpsPoint
from processing.wind import estimate_wind_axis_from_gps
from processing.wind_estimation import _nudge_with_gps_axis, weighted_fusion


def _track(headings, *, speed=5.0, t0=1000.0, dt=10.0):
    return [GpsPoint(timestamp=t0 + i * dt, lat=45.0, lon=9.0, speed_kts=speed, heading_deg=h)
            for i, h in enumerate(headings)]


def _beating(n=100, axis=0.0, tack_half=25.0):
    """Alternating tacks ``axis ± tack_half`` — a genuine windward beat."""
    return _track([(axis + tack_half) % 360 if i % 2 == 0 else (axis - tack_half) % 360
                   for i in range(n)])


# --- gating -----------------------------------------------------------------

def test_beat_yields_axis():
    est = estimate_wind_axis_from_gps(_beating(axis=0.0))
    assert est is not None
    axis_deg, conf = est
    # Axis is a line in [0,180); a beat about North gives ~0.
    assert min(axis_deg, 180 - axis_deg) < 8.0
    assert 0.0 < conf <= 1.0


def test_beat_about_oblique_axis():
    est = estimate_wind_axis_from_gps(_beating(axis=120.0))
    assert est is not None
    axis_deg, _ = est
    # 120° axis folds into [0,180) as 120.
    assert abs(axis_deg - 120.0) < 8.0


def test_steady_reach_is_gated_out():
    # One constant heading: high axis concentration but only ONE side sailed.
    assert estimate_wind_axis_from_gps(_track([70.0] * 100)) is None


def test_motoring_straight_is_gated_out():
    assert estimate_wind_axis_from_gps(_track([200.0] * 100)) is None


def test_single_tack_is_gated_out():
    # Only ever on one tack (all headings ~ axis+25) — can't reveal the wind.
    assert estimate_wind_axis_from_gps(_track([25.0] * 100)) is None


def test_too_short_returns_none():
    assert estimate_wind_axis_from_gps(_beating(n=40)) is None            # < 60 pts


def test_stationary_track_returns_none():
    # Beating headings but nearly stationary (below min_speed) -> too few moving points.
    stationary = _track([25.0 if i % 2 else 335.0 for i in range(100)], speed=0.5)
    assert estimate_wind_axis_from_gps(stationary) is None


# --- 180° resolution + low-weight, direction-only nudge ---------------------

def test_nudge_resolves_ambiguity_toward_fused_direction():
    # Axis 0 (line 0/180). Fused says ~10 -> resolve to 0, nudge 10 slightly down.
    rows = [{"twd_deg": 10.0, "tws_kts": 12.0, "confidence": 5.0}]
    _nudge_with_gps_axis(rows, axis_deg=0.0, gps_confidence=1.0)
    assert 8.0 < rows[0]["twd_deg"] < 10.0
    assert rows[0]["tws_kts"] == 12.0                 # speed untouched

    # Same axis, but fused says ~170 -> the OTHER end (180) is nearer.
    rows = [{"twd_deg": 170.0, "tws_kts": 8.0, "confidence": 5.0}]
    _nudge_with_gps_axis(rows, axis_deg=0.0, gps_confidence=1.0)
    assert 170.0 < rows[0]["twd_deg"] < 172.0


def test_nudge_is_low_weight_against_strong_consensus():
    rows = [{"twd_deg": 20.0, "tws_kts": 15.0, "confidence": 100.0}]
    _nudge_with_gps_axis(rows, axis_deg=0.0, gps_confidence=1.0)
    # A confident fused estimate barely moves.
    assert abs(rows[0]["twd_deg"] - 20.0) < 0.5


def test_weighted_fusion_applies_gps_nudge_end_to_end():
    bundle = [{
        "lat": 45.0, "lng": 9.0, "real_stations": [],
        "model_candidates": {"icon_d2": [
            {"observed_at": 1000, "twd_deg": 20, "tws_kts": 11},
            {"observed_at": 2000, "twd_deg": 20, "tws_kts": 11},
        ]},
        "grid_estimates": [],
    }]
    gps = _beating(n=100, axis=0.0)  # beats about North; timestamps 1000..1990
    series = weighted_fusion(gps, [], None, bundle)
    assert series and all(r["source"] == "fusion" for r in series)
    # A single regional model (modest weight) gets pulled from 20 toward the
    # GPS axis (0), but not past it.
    assert all(0.0 < r["twd_deg"] < 20.0 for r in series)
    assert all(r["tws_kts"] == pytest.approx(11.0, abs=0.5) for r in series)


def test_weighted_fusion_ignores_gps_when_not_beating():
    bundle = [{
        "lat": 45.0, "lng": 9.0, "real_stations": [],
        "model_candidates": {"icon_d2": [
            {"observed_at": 1000, "twd_deg": 20, "tws_kts": 11},
            {"observed_at": 2000, "twd_deg": 20, "tws_kts": 11},
        ]},
        "grid_estimates": [],
    }]
    gps = _track([70.0] * 100, t0=1000.0, dt=10.0)  # steady reach -> gated out
    series = weighted_fusion(gps, [], None, bundle)
    assert all(r["twd_deg"] == pytest.approx(20.0, abs=0.5) for r in series)
