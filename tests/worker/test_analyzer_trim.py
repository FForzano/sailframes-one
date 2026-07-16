"""Reversible track trim: ``_slice_by_time`` and ``load_session_context``/
``analyze_session`` accepting ``trim_start``/``trim_end``. The key
regression-safety property: both ``None`` (the common case, no trim set on
the session) must leave analysis byte-for-byte unaffected."""

import json
from pathlib import Path

import pytest

from analyzer import _slice_by_time, analyze_session, load_session_context
from processing.models import GpsPoint


def _gps(ts):
    return GpsPoint(timestamp=float(ts), lat=45.0, lon=9.0, speed_kts=5.0, heading_deg=0.0)


class TestSliceByTime:
    def test_no_bounds_is_noop(self):
        records = [_gps(t) for t in range(5)]
        assert _slice_by_time(records, None, None) is records

    def test_filters_dataclass_records_by_attribute(self):
        records = [_gps(t) for t in range(10)]
        sliced = _slice_by_time(records, 3, 6)
        assert [r.timestamp for r in sliced] == [3.0, 4.0, 5.0, 6.0]

    def test_filters_dict_records_by_key(self):
        """estimated_position/estimated_motion shape (track.py) — plain
        dicts, not dataclasses."""
        records = [{"timestamp": float(t), "lat": 0, "lon": 0} for t in range(10)]
        sliced = _slice_by_time(records, 3, 6)
        assert [r["timestamp"] for r in sliced] == [3.0, 4.0, 5.0, 6.0]

    def test_open_bounds(self):
        records = [_gps(t) for t in range(5)]
        assert [r.timestamp for r in _slice_by_time(records, 2, None)] == [2.0, 3.0, 4.0]
        assert [r.timestamp for r in _slice_by_time(records, None, 2)] == [0.0, 1.0, 2.0]


def _write_gps_json(data_dir: Path, n: int, t0: float = 1_800_000_000.0) -> float:
    """A straight-line track: n samples, one per second."""
    points = [
        {"timestamp": t0 + i, "lat": 45.0 + 0.0001 * i, "lon": 9.0 + 0.0001 * i,
         "speed_kts": 6.0, "heading_deg": 45.0}
        for i in range(n)
    ]
    (data_dir / "gps.json").write_text(json.dumps(points))
    return t0


class TestLoadSessionContextTrim:
    def test_trim_bounds_reduce_the_track(self, tmp_path):
        t0 = _write_gps_json(tmp_path, 30)
        ctx = load_session_context(tmp_path, trim_start=t0 + 10, trim_end=t0 + 20)
        assert ctx is not None
        assert len(ctx.gps) == 11  # inclusive [10, 20]
        assert ctx.gps[0].timestamp == pytest.approx(t0 + 10)
        assert ctx.gps[-1].timestamp == pytest.approx(t0 + 20)

    def test_no_trim_keeps_full_track(self, tmp_path):
        _write_gps_json(tmp_path, 30)
        ctx = load_session_context(tmp_path)
        assert ctx is not None
        assert len(ctx.gps) == 30


class TestAnalyzeSessionTrimRegression:
    def test_untrimmed_analysis_is_unaffected(self, tmp_path):
        """The load-bearing regression check: an existing (untrimmed)
        session's analysis must not change now that trim params exist."""
        _write_gps_json(tmp_path, 30)
        result_default = analyze_session(tmp_path)
        result_explicit_none = analyze_session(tmp_path, trim_start=None, trim_end=None)
        assert result_default["summary"] == result_explicit_none["summary"]

    def test_trimmed_analysis_reflects_only_the_window(self, tmp_path):
        t0 = _write_gps_json(tmp_path, 30)
        full = analyze_session(tmp_path)
        trimmed = analyze_session(tmp_path, trim_start=t0 + 10, trim_end=t0 + 20)
        assert trimmed["summary"]["duration_s"] < full["summary"]["duration_s"]
        assert trimmed["summary"]["duration_s"] == 10
