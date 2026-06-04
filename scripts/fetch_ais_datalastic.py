#!/usr/bin/env python3
"""Fetch historical AIS traffic for a race window from Datalastic and
normalize it into races/<race_id>/ais/vessels.json for the dashboard's
AIS obstacle overlay.

Datalastic flow (confirmed against the live API, June 2026):
  1. POST /api/v0/report  report_type=inradius_history  (lat/lon/radius +
     from/to DATES — day granularity) -> async job -> ZIP whose CSV is the
     POSITION TIME-SERIES (uuid,lat,lon,speed[0.1kn],course,heading,navstat,
     ...,last_pos_utc) for every vessel in the zone that day. ~20 fixes /
     vessel / day (coarse archive). This is our position source.
  2. GET /api/v0/vessel_history?uuid=...  -> per-vessel identity
     (name, mmsi, type, type_specific). One call per windowed vessel.

The historical archive is ~1 fix / 25-30 min, so the frontend linearly
interpolates between samples. We keep points within the race window +/- a
pad so interpolation has brackets at the edges.

Filtering (default): keep commercial + passenger vessels regardless of
motion (anchored tankers / docked ferries are still obstacles), plus any
other vessel that actually moved (>1.5 kt) during the window. This drops
the large docked recreational fleet inside the radius. --keep-all overrides.

Credits: inradius report ~= vessels-that-day (capped 500); vessel_history
= 1 credit / windowed vessel. A single race window is well under one
Starter month (20k credits). API key is read from $DATALASTIC_API_KEY —
never hard-code or commit it.

Example (full, hits the API):
  DATALASTIC_API_KEY=... python scripts/fetch_ais_datalastic.py \
    --race-id fa3cad05 --lat 42.350 --lon -71.010 --radius-nm 5 \
    --from 2026-06-03T22:35:00Z --to 2026-06-03T23:50:00Z \
    --out /tmp/ais_fa3cad05.json

Reuse an already-downloaded report CSV + identity cache (no new credits):
  ... --inradius-csv /tmp/inradius.csv --ident-cache /tmp/ident.json
"""
import argparse
import csv
import io
import json
import os
import sys
import time
import zipfile
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

BASE = "https://api.datalastic.com/api/v0"
PAD_MIN = 45        # keep samples this far outside the window for edge interpolation
MOVING_KT = 1.5     # >this SOG during the window => "moving" (kept even if recreational)


def _key():
    k = os.environ.get("DATALASTIC_API_KEY")
    if not k:
        sys.exit("ERROR: set DATALASTIC_API_KEY in the environment")
    return k


def _get(path, params):
    params = dict(params); params["api-key"] = _key()
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def _post_report(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{BASE}/report?api-key={_key()}", data=data,
                                headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _iso(dt): return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _piso(ts): return datetime.fromisoformat(ts.replace("Z", "+00:00"))
def _f(x, d=0.0):
    try: return float(x)
    except Exception: return d


def categorize(type_, type_specific):
    s = f"{type_ or ''} {type_specific or ''}".lower()
    if any(w in s for w in ("cargo", "tanker", "tug", "tow", "dredg", "pilot", "port tender")):
        return "commercial"
    if any(w in s for w in ("passenger", "high speed", "ferry")):
        return "passenger"
    if "sailing" in s:
        return "sailing"
    if "pleasure" in s:
        return "pleasure"
    return "other"


def submit_and_download_csv(lat, lon, radius_nm, day_from, day_to, poll_s=18, timeout_s=1800):
    resp = _post_report({"report_type": "inradius_history", "lat": lat, "lon": lon,
                         "radius": radius_nm, "from": day_from, "to": day_to})
    rid = resp["data"]["report_id"]
    print(f"  report_id={rid}", file=sys.stderr)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        d = _get("report", {"report_id": rid})["data"]
        d = d[0] if isinstance(d, list) and d else d
        st = d.get("status")
        if st == "_DONE_":
            with urllib.request.urlopen(d["result_url"], timeout=120) as r:
                zf = zipfile.ZipFile(io.BytesIO(r.read()))
            name = next(n for n in zf.namelist() if n.endswith(".csv"))
            return zf.open(name).read().decode("utf-8")
        if st in ("_FAILED_", "_ERROR_"):
            sys.exit(f"report failed: {d}")
        print(f"  ...{st}", file=sys.stderr)
        time.sleep(poll_s)
    sys.exit("report timed out")


def parse_positions(csv_text, win_lo, win_hi):
    """Group CSV rows by uuid -> sorted positions within [win_lo, win_hi]."""
    byv = {}
    for r in csv.DictReader(io.StringIO(csv_text)):
        if not r.get("uuid") or not r.get("lat") or not r.get("lon"):
            continue
        try:
            t = datetime.strptime(r["last_pos_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if not (win_lo <= t <= win_hi):
            continue
        hdg = r.get("heading")
        byv.setdefault(r["uuid"], []).append({
            "t": _iso(t),
            "lat": round(_f(r["lat"]), 6),
            "lon": round(_f(r["lon"]), 6),
            "sog": round(_f(r["speed"]) / 10.0, 1),   # CSV speed is 0.1-kn units
            "cog": round(_f(r["course"]), 1),
            "hdg": (int(_f(hdg)) if hdg not in (None, "", "511") and _f(hdg) != 511 else None),
            "nav": (r.get("navstat") or None),
        })
    for u in byv:
        byv[u].sort(key=lambda p: p["t"])
    return byv


def fetch_identity(uuid):
    d = _get("vessel_history", {"uuid": uuid, "from": "2026-01-01", "to": "2026-12-31"}).get("data", {})
    return {"name": d.get("name"), "mmsi": d.get("mmsi"),
            "type": d.get("type"), "type_specific": d.get("type_specific")}


def fetch_size(uuid):
    """vessel_info -> static dimensions for tonnage-based marker sizing.
    Small craft often have null fields (no registry data); the frontend
    falls back to length, then a type default."""
    d = _get("vessel_info", {"uuid": uuid}).get("data", {})
    def num(x):
        try: return round(float(x), 1)
        except Exception: return None
    return {"gross_tonnage": num(d.get("gross_tonnage")),
            "length_m": num(d.get("length")),
            "beam_m": num(d.get("breadth"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--race-id", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius-nm", type=float, default=5)
    ap.add_argument("--from", dest="t_from", required=True)
    ap.add_argument("--to", dest="t_to", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--inradius-csv", help="reuse a downloaded report CSV instead of submitting one")
    ap.add_argument("--ident-cache", help="JSON {uuid: {name,mmsi,type,type_specific}} to avoid re-fetching identity")
    ap.add_argument("--with-size", action="store_true", help="also fetch vessel_info per kept vessel for tonnage/length (marker sizing)")
    ap.add_argument("--size-cache", help="JSON {uuid: {gross_tonnage,length_m,beam_m}} to avoid re-fetching sizes")
    ap.add_argument("--keep-all", action="store_true", help="keep every in-window vessel (incl. docked recreational)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    win_start, win_end = _piso(args.t_from), _piso(args.t_to)
    win_lo = win_start - timedelta(minutes=PAD_MIN)
    win_hi = win_end + timedelta(minutes=PAD_MIN)
    day_from = win_start.astimezone(timezone.utc).strftime("%Y-%m-%d")
    day_to = (win_end.astimezone(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    if args.inradius_csv:
        csv_text = open(args.inradius_csv, encoding="utf-8").read()
    else:
        print(f"Submitting inradius_history report ({day_from}..{day_to}, r={args.radius_nm}NM)...", file=sys.stderr)
        csv_text = submit_and_download_csv(args.lat, args.lon, args.radius_nm, day_from, day_to)

    byv = parse_positions(csv_text, win_lo, win_hi)
    # vessels actually present DURING the race window (not just the pad)
    present = {u: pts for u, pts in byv.items()
               if any(win_start <= _piso(p["t"]) <= win_end for p in pts)}
    print(f"{len(present)} vessels in the race window", file=sys.stderr)
    if args.dry_run:
        print(f"DRY RUN: {len(present)} windowed vessels; would fetch identity for each.")
        return

    ident_cache, size_cache = {}, {}
    if args.ident_cache and os.path.exists(args.ident_cache):
        ident_cache = json.load(open(args.ident_cache))
    if args.size_cache and os.path.exists(args.size_cache):
        size_cache = json.load(open(args.size_cache))

    vessels, cats, dropped = [], {}, 0
    for i, (u, pts) in enumerate(present.items(), 1):
        meta = ident_cache.get(u) or fetch_identity(u)
        cat = categorize(meta.get("type"), meta.get("type_specific"))
        win_pts = [p for p in pts if win_start <= _piso(p["t"]) <= win_end]
        max_sog = max((p["sog"] for p in win_pts), default=0)
        moving = max_sog > MOVING_KT
        # Default filter: hazards (commercial/passenger) always; others only if moving.
        if not args.keep_all and cat in ("pleasure", "sailing", "other") and not moving:
            dropped += 1
            continue
        size = size_cache.get(u) or (fetch_size(u) if args.with_size else {})
        cats[cat] = cats.get(cat, 0) + 1
        vessels.append({
            "mmsi": meta.get("mmsi") or u[:8],
            "name": (meta.get("name") or "").strip() or "(unknown)",
            "category": cat,
            "type_raw": meta.get("type_specific") or meta.get("type") or "",
            "moving": moving,
            "gross_tonnage": size.get("gross_tonnage"),
            "length_m": size.get("length_m"),
            "beam_m": size.get("beam_m"),
            "positions": pts,
        })

    doc = {
        "source": "datalastic",
        "generated_at": _iso(datetime.now(timezone.utc)),
        "center": {"lat": args.lat, "lon": args.lon},
        "radius_nm": args.radius_nm,
        "window": {"start": _iso(win_start), "end": _iso(win_end)},
        "vessels": vessels,
    }
    json.dump(doc, open(args.out, "w"), indent=2)
    print(f"\nWrote {len(vessels)} vessels to {args.out} (dropped {dropped} stationary recreational)")
    print("By category:", cats)


if __name__ == "__main__":
    main()
