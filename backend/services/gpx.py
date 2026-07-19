"""GPX track parsing/writing ↔ processed ``gps.json`` point format."""

import re
import xml.etree.ElementTree as ET

from . import geo

_GPX_NS = "http://www.topografix.com/GPX/1/1"
_KN_TO_MS = 1 / 1.94384


def parse_gpx(content: bytes) -> list[dict]:
    """Parse GPX XML into GPS track points matching the processed gps.json
    format (``t``, ``lat``, ``lon``, ``speed_kn``, ``course``)."""
    root = ET.fromstring(content)
    ns_match = re.match(r"\{([^}]+)\}", root.tag)
    ns = f"{{{ns_match.group(1)}}}" if ns_match else ""

    raw: list[dict] = []
    for seg in root.iter(f"{ns}trkseg"):
        for trkpt in seg.iter(f"{ns}trkpt"):
            lat = float(trkpt.get("lat", 0))
            lon = float(trkpt.get("lon", 0))
            time_el = trkpt.find(f"{ns}time")
            if time_el is None or not time_el.text:
                continue
            t = time_el.text.strip()

            speed_ms = None
            for el in trkpt.iter():
                local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                if local == "speed" and el.text:
                    try:
                        speed_ms = float(el.text)
                    except ValueError:
                        pass
                    break

            if raw and raw[-1]["t"] == t and raw[-1]["lat"] == lat and raw[-1]["lon"] == lon:
                continue  # some exporters (e.g. Waterspeed) repeat a fix verbatim

            raw.append({"lat": lat, "lon": lon, "t": t, "_speed_ms": speed_ms})

    result = []
    for i, pt in enumerate(raw):
        sog = 0.0
        cog = 0.0

        if pt["_speed_ms"] is not None:
            sog = pt["_speed_ms"] * 1.94384  # m/s → knots
        elif i > 0:
            prev = raw[i - 1]
            try:
                dt = geo.iso_diff_seconds(pt["t"], prev["t"])
                if dt > 0:
                    dist_m = geo.haversine_m(prev["lat"], prev["lon"], pt["lat"], pt["lon"])
                    sog = (dist_m / dt) * 1.94384
            except Exception:
                pass

        if i > 0:
            prev = raw[i - 1]
            cog = geo.bearing(prev["lat"], prev["lon"], pt["lat"], pt["lon"])
        elif i < len(raw) - 1:
            nxt = raw[i + 1]
            cog = geo.bearing(pt["lat"], pt["lon"], nxt["lat"], nxt["lon"])

        result.append({
            "t": pt["t"],
            "lat": pt["lat"],
            "lon": pt["lon"],
            "speed_kn": round(sog, 2),
            "course": round(cog, 1),
        })

    return result


def build_gpx(points: list[dict]) -> bytes:
    """Serialize processed gps.json points (``t``/``lat``/``lon``/``speed_kn``)
    into GPX 1.1 XML — the inverse of ``parse_gpx``, used for the "download
    GPX" export (always regenerated from the processed track, never the
    original raw upload). ``<speed>`` is written in m/s — the unit
    ``parse_gpx`` reads it back as (``_speed_ms * 1.94384`` → knots) — so a
    round trip through both functions recovers the same knots value.
    ``course`` isn't written: ``parse_gpx`` never reads it from XML, it
    recomputes bearing from consecutive points itself."""
    gpx = ET.Element("gpx", {"version": "1.1", "creator": "SailFrames One", "xmlns": _GPX_NS})
    trkseg = ET.SubElement(ET.SubElement(gpx, "trk"), "trkseg")
    for p in points:
        trkpt = ET.SubElement(trkseg, "trkpt", {"lat": str(p["lat"]), "lon": str(p["lon"])})
        if p.get("t"):
            ET.SubElement(trkpt, "time").text = str(p["t"])
        if p.get("speed_kn") is not None:
            ET.SubElement(trkpt, "speed").text = str(p["speed_kn"] * _KN_TO_MS)
    return ET.tostring(gpx, encoding="utf-8", xml_declaration=True)
