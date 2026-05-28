#!/usr/bin/env python3
"""
Seed the 2026 Constitution YC Wednesday Evening Spring Series — Race 1
(2026-05-27). Multi-class handicap race with PHRF ratings; all entries
loaded from regattaman.com's Preliminary results sheet.

GPS device_id is left null on every boat — the user assigns E1..E6 to
specific entries via the race editor once they confirm which physical
tracker rode on which boat.

Idempotent: re-running PATCHes the existing race in place (matched on
regatta_id + date + name "Race 1").

Usage:
    python3 scripts/seed_cyc_wed_spring_2026.py

Requires the api_race Lambda to have been redeployed with the
classes / race_conditions fields supported; otherwise the POST/PATCH
will succeed but those fields silently drop.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = "https://rnngzx7flk.execute-api.us-east-1.amazonaws.com"

# DST: 2026-05-27 falls in EDT = UTC-4. Local-to-UTC offset is +4h.
LOCAL_TO_UTC = timedelta(hours=4)
RACE_DATE = "2026-05-27"

# Course (informational — not yet wired into race.course mark sequence):
#   S/F > 13S > D/M > 13P > S/F
#   Start/Finish line, leave mark 13 to starboard, round D/M, leave 13
#   to port, back to S/F. Windward-leeward style course, hence the
#   "W50/L50 - Medium" rating type.
#
# Rating system is ORR-EZ (Offshore Racing Rule – EZ) operated by
# regattaman.com. Per-boat certificate URLs are baked in via
# CERT_URLS below — captured on 2026-05-28 from the published list.
RATING_SYSTEM = "ORR-EZ"
RATING_TYPE = "W50/L50 - Medium"
RACE_LEN_NM = 3.50


# ORR-EZ certificate URLs by sail number. Sourced from
# https://www.regattaman.com/cert_list.php on 2026-05-28. Boats not in
# this map have no published cert in the 2026 EZ list yet — the user
# can paste a URL into the boat's catalog page manually.
CERT_URLS = {
    'USA 14':    'https://www.regattaman.com/cert_form.php?sku=h-2-2026-10665-15632-0-579',
    '61430':     'https://www.regattaman.com/cert_form.php?sku=h-2-2026-1-3758-0-579',
    'USA 78':    'https://www.regattaman.com/cert_form.php?sku=h-2-2026-7173-15690-0-579',
    '51613':     'https://www.regattaman.com/cert_form.php?sku=h-2-2026-526-530-0-579',
    '52475':     'https://www.regattaman.com/cert_form.php?sku=h-2-2026-178-275-0-579',
    '52816':     'https://www.regattaman.com/cert_form.php?sku=h-2-2026-194-2487-0-579',
    'USA 40':    'https://www.regattaman.com/cert_form.php?sku=h-1-2026-15431-19173-0-579',
    'USA 1111':  'https://www.regattaman.com/cert_form.php?sku=h-2-2026-1655-18035-0-579',
    '7':         'https://www.regattaman.com/cert_form.php?sku=h-2-2026-4265-7801-0-579',
    '470':       'https://www.regattaman.com/cert_form.php?sku=h-22-2026-17418-14372-0-579',
    '110':       'https://www.regattaman.com/cert_form.php?sku=h-2-2026-16372-12961-0-579',
    '4396':      'https://www.regattaman.com/cert_form.php?sku=h-2-2026-222-15935-0-579',
    '220':       'https://www.regattaman.com/cert_form.php?sku=h-41-2026-18229-15922-0-579',
}


def local_iso(hms: str) -> str:
    """'18:41:00' local EDT → '2026-05-27T22:41:00Z' UTC."""
    h, m, s = map(int, hms.split(":"))
    dt = datetime(2026, 5, 27, h, m, s) + LOCAL_TO_UTC
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


# ---------- Regatta + race meta ----------

REGATTA = {
    "name": "2026 Constitution YC Wednesday Evening Spring Series",
    "venue": "Boston Harbor — Constitution Yacht Club",
    "start_date": "2026-05-27",
    "end_date": "2026-07-01",
}

CLASSES = [
    {
        "id": "A",
        "name": "Class A",
        "start_time": local_iso("18:41:00"),
        "rating_system": RATING_SYSTEM,
        "rating_type": RATING_TYPE,
        "race_len_nm": RACE_LEN_NM,
    },
    {
        "id": "B",
        "name": "Class B",
        "start_time": local_iso("18:35:00"),
        "rating_system": RATING_SYSTEM,
        "rating_type": RATING_TYPE,
        "race_len_nm": RACE_LEN_NM,
    },
]


def _split_skippers(team_name):
    """'Paul Avillach & Kathryn Commons' → ['Paul Avillach', 'Kathryn Commons'].
    Trims to 2; longer combos drop the tail (rare for sailing fleets)."""
    if not team_name:
        return []
    # Split on '&' or ' and '. Each part trimmed.
    import re
    parts = [p.strip() for p in re.split(r'\s*&\s*|\s+and\s+', team_name) if p.strip()]
    return [{"name": p, "photo": None} for p in parts[:2]]


def _boat(cls, team, yacht, club, sail_no, boat_type, rating,
          finish_hms=None, status="FIN"):
    return {
        "device_id": None,           # user assigns in editor
        "class": cls,
        "rating": rating,
        "team_name": team,           # this race's skipper (legacy field)
        "boat_name": yacht,
        "sail_number": sail_no,
        "boat_type": boat_type,
        "club": club,
        "finish_time": local_iso(finish_hms) if finish_hms else None,
        "finish_status": status,
        "session_path": None,
        "gpx_path": None,
    }


# Known boat-type → LOA (metres). The seed script attaches these to
# the boat catalog so the dashboard can size each hull correctly on
# the map. Source: manufacturer specs / sailboatdata.com. Extend as
# new types enter the fleet.
BOAT_TYPE_LOA = {
    "J/92":                       9.14,
    "J/80":                       8.00,
    "J/30":                       9.14,
    "J/99":                       9.99,
    "J/109":                     10.81,
    "J/46 DK":                   14.02,
    "Arcona 430":                13.10,
    "Beneteau 36.7":             11.20,
    "Columbia 30-2 Sport":        9.14,
    "Frers 38":                  11.58,
    "Buzzards Bay 30":            9.14,
    "Pearson 33-2":              10.06,
    "Jeanneau Sun Odyssey 410":  12.45,
    "Sabre 34 MK1":              10.36,
}


# ---------- Boats — from the corrected Preliminary results sheet ----------
# Ratings are W50/L50 - Medium (NOT the Random Leg values from the first
# sheet). Pogue / Never Settle is in Class A. Katü's skipper is now
# Paul Avillach & Kathryn Commons.

BOATS = [
    # Class A — start 18:41:00
    _boat("A", "Pogue, Robert", "Never Settle", "Constitution YC",
          "USA 14", "J/92", 0.915, "19:14:20"),
    _boat("A", "Alexander, Dave", "Pressure Drop", "Constitution YC",
          "61430", "Arcona 430", 0.939, "19:17:32"),
    _boat("A", "Isaacson, Peter", "Uproarious", "Constitution YC",
          "USA 78", "J/109", 0.929, "19:19:00"),
    _boat("A", "Jacobson, William", "VANISH", "Constitution YC",
          "51613", "J/46 DK", 0.992, "19:17:18"),
    _boat("A", "Powers, David and Tom / Crimmins, Joe", "Agora",
          "New York YC / Constitution YC", "52475", "Beneteau 36.7",
          0.931, "19:19:51"),
    _boat("A", "Ryley, Lance", "RockIt 2.0", "Constitution YC",
          "52816", "Columbia 30-2 Sport", 0.962, "19:19:54"),
    _boat("A", "Rudser, Jim", "Riot", "Constitution YC",
          "USA 40", "J/99", 0.938, "19:24:58"),
    _boat("A", "McLean, Allan", "Eagle", "Constitution YC",
          "42359", "Frers 38", 0.899, "19:34:31"),
    # DNC kept from prior week's roster — not visible in the updated
    # sheet (only racers + RET shown) but # of Entries: 9 confirms
    # there's a 9th boat. Rating reused from Isaacson's J/109 since
    # both are J/109s on the same scoring scheme.
    _boat("A", "Barmmer, Brian", "Saorsa", "Boston YC",
          "USA 1111", "J/109", 0.929, status="DNC"),

    # Class B — start 18:35:00
    _boat("B", "Conway, Ryan", "MASHNEE", "MIT Nautical Assoc.",
          "7", "Buzzards Bay 30", 0.862, "19:20:32"),
    _boat("B", "De Souter, Marissa & Wafler, Garrett", "Special Sauce", "",
          "470", "J/30", 0.848, "19:21:21"),
    # Katü — skippered by Paul Avillach (yes, you) and Kathryn Commons.
    _boat("B", "Paul Avillach & Kathryn Commons", "Katü", "Courageous SC",
          "484", "J/80", 0.872, "19:20:25"),
    _boat("B", "DiLorenzo, Dave", "Amigo", "",
          "82", "J/80", 0.872, "19:21:00"),
    _boat("B", "Phelps, Isaac", "Seabiscuit", "Constitution YC",
          "110", "Pearson 33-2", 0.824, "19:30:34"),
    _boat("B", "Tubman, Richard", "Charisma", "Constitution YC",
          "4396", "Jeanneau Sun Odyssey 410", 0.851, "19:30:41"),
    _boat("B", "Long, III, James Gardner & Wagner, Ryan", "Badger",
          "Constitution YC", "220", "Sabre 34 MK1", 0.731, status="RET"),
    # DNC entries not shown in the visible sheet rows but accounted for
    # by # of Entries: 9. Rating bumped to 0.872 to match the other
    # J/80s on the new W50/L50 scale.
    _boat("B", "DiLorenzo, Dave", "Wizard", "",
          "811", "J/80", 0.872, status="DNC"),
    _boat("B", "DiLorenzo, Dave & Sailing, Courageous", "Doc Buck",
          "Courageous SC", "88", "J/80", 0.872, status="DNC"),
]


# ---------- HTTP helpers ----------

def _request(method, path, body=None):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "ignore")
        print(f"  HTTP {e.code} on {method} {url}: {body_txt}", file=sys.stderr)
        raise


def find_or_create_regatta():
    _, data = _request("GET", "/api/regattas")
    for r in data.get("regattas", []):
        if r["name"] == REGATTA["name"]:
            print(f"  Reusing existing regatta {r['regatta_id']} — {r['name']}")
            return r["regatta_id"]
    print(f"  Creating regatta: {REGATTA['name']}")
    _, created = _request("POST", "/api/regattas", REGATTA)
    return created["regatta_id"]


def find_existing_race(regatta_id):
    _, data = _request("GET", f"/api/races?regatta_id={regatta_id}&date={RACE_DATE}")
    for r in data.get("races", []):
        if r.get("name") == "Race 1":
            return r["race_id"]
    return None


def find_or_create_boat(boat_entry):
    """Find a catalog boat by sail_number, else create one. Returns
    boat_id. Updates the catalog's loa_m / type / skippers / cert
    fields to the latest seed values (idempotent re-sync)."""
    sail = (boat_entry.get("sail_number") or "").strip()
    if not sail:
        # No sail number → don't try to dedupe; just create. The
        # eventual user can clean these up by hand.
        return _create_boat_doc(boat_entry)

    _, data = _request("GET", f"/api/boats?sail_number={urllib.parse.quote(sail)}")
    matches = data.get("boats", [])
    if matches:
        boat_id = matches[0]["boat_id"]
        patch = {
            "name": boat_entry.get("boat_name") or matches[0].get("name", ""),
            "type": boat_entry.get("boat_type") or matches[0].get("type", ""),
            "loa_m": BOAT_TYPE_LOA.get(boat_entry.get("boat_type")) or matches[0].get("loa_m"),
            "club": boat_entry.get("club") or matches[0].get("club", ""),
            "skippers": _split_skippers(boat_entry.get("team_name", "")),
            "cert_url": CERT_URLS.get(sail) or matches[0].get("cert_url", ""),
        }
        _request("PATCH", f"/api/boats/{boat_id}", patch)
        return boat_id

    return _create_boat_doc(boat_entry)


def _create_boat_doc(boat_entry):
    sail = (boat_entry.get("sail_number") or "").strip()
    body = {
        "name": boat_entry.get("boat_name", ""),
        "type": boat_entry.get("boat_type", ""),
        "sail_number": boat_entry.get("sail_number", ""),
        "club": boat_entry.get("club", ""),
        "loa_m": BOAT_TYPE_LOA.get(boat_entry.get("boat_type")),
        "skippers": _split_skippers(boat_entry.get("team_name", "")),
        "photos": {"boat": None, "skipper1": None, "skipper2": None},
        "cert_url": CERT_URLS.get(sail, ""),
        "links": [],
        "notes": "",
    }
    _, created = _request("POST", "/api/boats", body)
    return created["boat_id"]


def main():
    print("Seeding CYC Wednesday Spring Series — Race 1 (2026-05-27)")
    regatta_id = find_or_create_regatta()

    # Upsert every boat into the catalog, building a parallel array
    # of (boat_id, race_entry) pairs. boat_id rides on the race entry
    # so the dashboard can hydrate catalog metadata at load time.
    print(f"  Upserting {len(BOATS)} boats into catalog…")
    boats_with_ids = []
    for b in BOATS:
        bid = find_or_create_boat(b)
        b2 = dict(b)
        b2["boat_id"] = bid
        # Stamp LOA on the race entry too so old-frontend snapshots
        # (pre-hydration) still get a usable per-boat hull size.
        loa = BOAT_TYPE_LOA.get(b.get("boat_type"))
        if loa is not None:
            b2["loa_m"] = loa
        boats_with_ids.append(b2)

    existing = find_existing_race(regatta_id)
    race_payload = {
        "name": "Race 1",
        "date": RACE_DATE,
        # Playback timeline starts at first gun (warning signal). Per-class
        # start times in classes[] are what PHRF elapsed is measured from.
        "start_time": local_iso("18:30:00"),
        "end_time": local_iso("19:40:00"),
        "regatta_id": regatta_id,
        "classes": CLASSES,
        "race_conditions": "WNW 12 kts",
        "boats": boats_with_ids,
    }

    if existing:
        print(f"  Updating existing race {existing}")
        # Preserve user-set device_id / session_path / gpx_path on any
        # boat already in the race (matched by sail_number). Re-running
        # the seed must not wipe GPS tracker assignments or attached
        # sessions/GPX files.
        _, prior = _request("GET", f"/api/races/{existing}")
        prior_by_sail = {(b.get("sail_number") or "").strip(): b
                         for b in prior.get("boats", [])}
        for b in race_payload["boats"]:
            old = prior_by_sail.get((b.get("sail_number") or "").strip())
            if not old:
                continue
            if old.get("device_id"):     b["device_id"] = old["device_id"]
            if old.get("session_path"):  b["session_path"] = old["session_path"]
            if old.get("gpx_path"):      b["gpx_path"] = old["gpx_path"]
        _, race = _request("PATCH", f"/api/races/{existing}", race_payload)
    else:
        print("  Creating new race")
        _, race = _request("POST", "/api/races", race_payload)

    race_id = race["race_id"]
    print()
    print(f"✓ Race seeded: {race_id}")
    print(f"  Dashboard: https://sailframes.com/race.html?race={race_id}")
    print(f"  {len(BOATS)} boats across {len(CLASSES)} classes")
    n_a = sum(1 for b in BOATS if b['class'] == 'A')
    n_b = sum(1 for b in BOATS if b['class'] == 'B')
    n_fin = sum(1 for b in BOATS if b['finish_status'] == 'FIN')
    print(f"  Class A: {n_a} entries · Class B: {n_b} entries · {n_fin} finishers")
    print()
    print("Next: open the dashboard, edit the race, assign device_id")
    print("(E1..E6) to whichever boats actually carried GPS trackers.")


if __name__ == "__main__":
    main()
