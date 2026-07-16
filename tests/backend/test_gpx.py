"""GPX round trip: ``build_gpx`` (the "download GPX" writer) is the inverse
of ``parse_gpx``, the existing reader — a point serialized then reparsed
must recover the same lat/lon/speed (course is recomputed from bearing by
``parse_gpx``, never read from XML, so it isn't part of the round trip)."""

import pytest

from backend.services.gpx import build_gpx, parse_gpx


def _points():
    return [
        {"t": "2026-07-16T10:00:00+00:00", "lat": 45.1, "lon": 9.1,
         "speed_kn": 6.5, "course": 90.0},
        {"t": "2026-07-16T10:00:01+00:00", "lat": 45.1001, "lon": 9.1001,
         "speed_kn": 6.7, "course": 91.0},
        {"t": "2026-07-16T10:00:02+00:00", "lat": 45.1002, "lon": 9.1002,
         "speed_kn": 6.9, "course": 92.0},
    ]


def test_round_trip_recovers_lat_lon_speed():
    points = _points()
    reparsed = parse_gpx(build_gpx(points))
    assert len(reparsed) == len(points)
    for orig, rt in zip(points, reparsed):
        assert rt["lat"] == pytest.approx(orig["lat"])
        assert rt["lon"] == pytest.approx(orig["lon"])
        assert rt["speed_kn"] == pytest.approx(orig["speed_kn"], abs=0.01)


def test_output_is_valid_gpx_xml():
    gpx_bytes = build_gpx(_points())
    assert gpx_bytes.startswith(b"<?xml")
    assert b"<gpx" in gpx_bytes
    assert gpx_bytes.count(b"<trkpt") == 3


def test_empty_track():
    assert parse_gpx(build_gpx([])) == []
