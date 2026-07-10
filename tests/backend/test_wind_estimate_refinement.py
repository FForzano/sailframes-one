"""Backend grid refiner: weighted_merge blends the existing cell estimate
with a new observation and accumulates provenance."""

import pytest

from backend.services import wind_estimate_refinement as wer


def _obs(twd, tws, *, gust=None, type="onboard_sensor", session="s1"):
    return {"twd_deg": twd, "tws_kts": tws, "gust_kts": gust,
            "type": type, "session_id": session, "observed_at": "2026-07-09T12:00:00+00:00"}


def test_first_observation_writes_through():
    out = wer.weighted_merge(None, _obs(120, 10, gust=14))
    assert out["twd_deg"] == pytest.approx(120)
    assert out["tws_kts"] == pytest.approx(10)
    assert out["gust_kts"] == pytest.approx(14)
    assert out["confidence"] is not None and out["confidence"] > 0
    assert len(out["sources"]) == 1
    assert out["sources"][0]["session_id"] == "s1"


def test_merge_blends_and_accumulates_sources():
    existing = wer.weighted_merge(None, _obs(10, 10, gust=12, session="s1"))
    merged = wer.weighted_merge(existing, _obs(30, 10, gust=16, session="s2"))
    # Direction fuses between the two (vector mean), stays near ~20.
    assert 10 < merged["twd_deg"] < 30
    # Both provenance entries retained.
    assert {s["session_id"] for s in merged["sources"]} == {"s1", "s2"}
    # Gust is a weighted mean of the two.
    assert 12 < merged["gust_kts"] < 16


def test_confidence_compounds_across_refinements():
    e1 = wer.weighted_merge(None, _obs(10, 10))
    e2 = wer.weighted_merge(e1, _obs(10, 10))
    e3 = wer.weighted_merge(e2, _obs(10, 10))
    assert e3["confidence"] > e2["confidence"] > e1["confidence"]


def test_merge_wraps_direction_across_zero():
    existing = wer.weighted_merge(None, _obs(350, 10))
    merged = wer.weighted_merge(existing, _obs(10, 10))
    # Two equal-weight readings at 350 and 10 -> ~0/360, never ~180.
    assert merged["twd_deg"] > 340 or merged["twd_deg"] < 20


def test_merge_without_speed_keeps_existing_but_records_source():
    existing = wer.weighted_merge(None, _obs(100, 12))
    # A direction-only observation (no tws) can't fuse into the vector mean.
    merged = wer.weighted_merge(existing, _obs(200, None, session="dir_only"))
    assert merged["tws_kts"] == pytest.approx(12)      # existing speed kept
    assert merged["twd_deg"] == pytest.approx(100)     # existing direction kept
    assert any(s.get("session_id") == "dir_only" for s in merged["sources"])


def test_refine_dispatches_to_active_strategy():
    assert wer.ACTIVE_STRATEGY == "weighted_merge"
    out = wer.refine(None, _obs(45, 8))
    assert out["twd_deg"] == pytest.approx(45)
