"""Race endpoints (``/api/races*``).

A race owns its course (marks), entrants (boats), start/finish lines and
computed results. This router also hosts the race sub-resources: time-aligned
multi-boat data, session matching, per-boat GPX upload, and the start-line /
marks auto-suggestion. Cross-entity bookkeeping (linking a race into its race
day / regatta) goes through the repository layer.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from ..auth import require_admin
from ..schemas import RaceCreateModel, RaceUpdateModel
from ..services import course, geo, gpx
from ._common import (
    blob,
    get_race_dict,
    load_json_or_empty,
    now_iso,
    repos,
    save_json,
    save_race_dict,
)

router = APIRouter(prefix="/api/races", tags=["races"])


# --- Local helpers --------------------------------------------------------

def _find_device_sessions(device_id: str, date: str) -> list[dict]:
    """Find all sessions for a device on a given date."""
    sessions = []

    # Look for manifest files in processed folder
    prefix = f"processed/{device_id}/{date}"

    for key in blob.list_keys(prefix):
        if not key.endswith("/manifest.json"):
            continue
        try:
            manifest = blob.get_json(key)
            # Extract session folder from key (.../{session_folder}/manifest.json)
            session_folder = key.split("/")[-2]
            sessions.append({
                "session_path": f"{date}/{session_folder}",
                "start_time": manifest.get("start_time", ""),
                "end_time": manifest.get("end_time", ""),
            })
        except Exception:
            pass

    return sessions


def _load_race_gps(race_data: dict) -> dict:
    """Return ``{device_id: [gps_points]}`` for all boats with session data,
    filtered to the race window. GPS series live in the blob store."""
    start_time = race_data["start_time"]
    end_time = race_data["end_time"]
    out = {}
    for boat in race_data.get("boats", []):
        device_id = boat["device_id"]
        session_path = boat.get("session_path")
        if not session_path:
            continue
        key = f"processed/{device_id}/{session_path}/gps.json"
        data = load_json_or_empty(key)
        if not isinstance(data, list):
            continue
        filtered = [d for d in data if start_time <= d.get("t", "") <= end_time]
        if filtered:
            out[device_id] = filtered
    return out


def _in_window(t: str, start: str, end: str) -> bool:
    """Compare ISO timestamps defensively (ignores trailing Z / millis)."""
    def _norm(value: str) -> str:
        return (value or "").replace("Z", "").split(".")[0]

    tn = _norm(t)
    sn = _norm(start)
    en = _norm(end)
    if not (tn and sn and en):
        return False
    return sn <= tn <= en


# --- Race CRUD ------------------------------------------------------------

@router.get("")
def list_races(regatta_id: Optional[str] = None, date: Optional[str] = None, raceday_id: Optional[str] = None):
    """List all races, optionally filtered by regatta, date, or race day."""
    races = repos.races.list_summaries(regatta_id=regatta_id, date=date, raceday_id=raceday_id)
    return {"races": sorted(races, key=lambda r: (r.get("date", ""), r.get("start_time", "")))}


@router.get("/{race_id}")
def get_race(race_id: str):
    """Get a single race by ID."""
    race = repos.races.get(race_id)
    if race is None:
        raise HTTPException(404, f"Race not found: {race_id}")
    return race.to_dict()


@router.post("")
def create_race(race: RaceCreateModel, request: Request):
    """Create a new race."""
    require_admin(request)
    now = now_iso()
    rid = str(uuid.uuid4())[:8]
    repos.races.save_dict({
        "race_id": rid,
        "name": race.name,
        "date": race.date,
        "start_time": race.start_time,
        "end_time": race.end_time,
        "regatta_id": race.regatta_id,
        "raceday_id": race.raceday_id,
        "boats": [b.model_dump() for b in race.boats],
        "start_line": race.start_line.model_dump() if race.start_line else None,
        "finish_line": race.finish_line.model_dump() if race.finish_line else None,
        "marks": [m.model_dump() for m in race.marks],
        "course": race.course,
        "finish_order": race.finish_order,
        "results": None,
        "created_at": now,
        "updated_at": now,
    })

    # Link race into its race day / regatta (cross-entity bookkeeping).
    if race.raceday_id:
        day = repos.racedays.get(race.raceday_id)
        if day and rid not in day.race_ids:
            repos.racedays.update(race.raceday_id, {"race_ids": list(day.race_ids) + [rid], "updated_at": now})

    if race.regatta_id:
        regatta = repos.regattas.get(race.regatta_id)
        if regatta and rid not in regatta.race_ids:
            repos.regattas.update(race.regatta_id, {"race_ids": list(regatta.race_ids) + [rid], "updated_at": now})

    return repos.races.get(rid).to_dict()


@router.patch("/{race_id}")
def update_race(race_id: str, update: RaceUpdateModel, request: Request):
    """Update a race."""
    require_admin(request)
    race = repos.races.get(race_id)
    if race is None:
        raise HTTPException(404, f"Race not found: {race_id}")
    d = race.to_dict()

    if update.name is not None:
        d["name"] = update.name
    if update.start_time is not None:
        d["start_time"] = update.start_time
    if update.end_time is not None:
        d["end_time"] = update.end_time
    if update.boats is not None:
        d["boats"] = [b.model_dump() for b in update.boats]
    if update.start_line is not None:
        d["start_line"] = update.start_line.model_dump()
    if update.finish_line is not None:
        d["finish_line"] = update.finish_line.model_dump()
    if update.marks is not None:
        d["marks"] = [m.model_dump() for m in update.marks]
    if update.course is not None:
        d["course"] = update.course
    if update.finish_order is not None:
        d["finish_order"] = update.finish_order
    if update.raceday_id is not None:
        d["raceday_id"] = update.raceday_id or None

    d["updated_at"] = now_iso()
    repos.races.save_dict(d)
    return repos.races.get(race_id).to_dict()


@router.delete("/{race_id}")
def delete_race(race_id: str, request: Request):
    """Delete a race."""
    require_admin(request)
    race = repos.races.get(race_id)
    if race is None:
        raise HTTPException(404, f"Race not found: {race_id}")

    repos.races.delete(race_id)

    # Unlink from regatta if linked
    if race.regatta_id:
        regatta = repos.regattas.get(race.regatta_id)
        if regatta:
            repos.regattas.update(race.regatta_id, {
                "race_ids": [r for r in regatta.race_ids if r != race_id],
                "updated_at": now_iso(),
            })

    return {"deleted": race_id}


# --- Multi-Boat Data Endpoint ---------------------------------------------

@router.get("/{race_id}/data")
def get_race_data(
    race_id: str,
    sensors: str = Query("gps,imu,wind", description="Comma-separated sensors to load"),
    pad_start: int = Query(0, ge=0, description="Seconds to extend before race start"),
    pad_end: int = Query(0, ge=0, description="Seconds to extend after race end"),
):
    """
    Load time-aligned sensor data for all boats in a race.

    Returns data filtered to race time window for each boat that has
    a matched session.
    """
    race_data = get_race_dict(race_id)
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    start_time = race_data["start_time"]
    end_time = race_data["end_time"]
    filter_start = start_time
    filter_end = end_time
    if pad_start > 0 or pad_end > 0:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            filter_start = (start_dt - timedelta(seconds=pad_start)).isoformat().replace("+00:00", "Z")
            filter_end = (end_dt + timedelta(seconds=pad_end)).isoformat().replace("+00:00", "Z")
        except Exception:
            filter_start = start_time
            filter_end = end_time
    requested_sensors = [s.strip() for s in sensors.split(",")]

    boats_data = {}

    for boat in race_data.get("boats", []):
        device_id = boat["device_id"]
        session_path = boat.get("session_path")
        gpx_path = boat.get("gpx_path")

        if not session_path and not gpx_path:
            boats_data[device_id] = {"error": "No session matched", "boat": boat}
            continue

        boat_sensors = {}
        for sensor in requested_sensors:
            # GPX upload replaces the GPS sensor for this boat
            if sensor == "gps" and gpx_path:
                try:
                    data = load_json_or_empty(gpx_path)
                    if isinstance(data, list):
                        filtered = [
                            d for d in data
                            if _in_window(d.get("t", ""), filter_start, filter_end)
                        ]
                        boat_sensors[sensor] = filtered
                    else:
                        boat_sensors[sensor] = []
                except Exception as e:
                    boat_sensors[sensor] = {"error": str(e)}
                continue

            if not session_path:
                boat_sensors[sensor] = []
                continue

            try:
                sensor_key = f"processed/{device_id}/{session_path}/{sensor}.json"
                data = load_json_or_empty(sensor_key)
                if isinstance(data, list):
                    filtered = [
                        d for d in data
                        if _in_window(d.get("t", ""), filter_start, filter_end)
                    ]
                    boat_sensors[sensor] = filtered
                else:
                    boat_sensors[sensor] = data
            except Exception as e:
                boat_sensors[sensor] = {"error": str(e)}

        boats_data[device_id] = {
            "boat": boat,
            "sensors": boat_sensors,
        }

    return {
        "race": {
            "race_id": race_id,
            "name": race_data["name"],
            "date": race_data["date"],
            "start_time": start_time,
            "end_time": end_time,
        },
        "boats": boats_data,
        "time_bounds": {
            "start": start_time,
            "end": end_time,
        },
    }


@router.get("/{race_id}/gpx-status")
def get_gpx_status(race_id: str):
    """Return per-boat GPX import summary for debug and QA."""
    race_data = get_race_dict(race_id)
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    start_time = race_data.get("start_time", "")
    end_time = race_data.get("end_time", "")
    boats = []

    for boat in race_data.get("boats", []):
        device_id = boat.get("device_id")
        if not device_id:
            continue
        gpx_path = boat.get("gpx_path")
        entry = {"device_id": device_id, "gpx_path": gpx_path}
        if not gpx_path:
            entry["status"] = "no_gpx"
            boats.append(entry)
            continue

        data = load_json_or_empty(gpx_path)
        if not isinstance(data, list) or not data:
            entry["status"] = "empty"
            boats.append(entry)
            continue

        in_window = [d for d in data if _in_window(d.get("t", ""), start_time, end_time)]
        entry.update({
            "status": "ok",
            "total_points": len(data),
            "points_in_window": len(in_window),
            "track_start": data[0].get("t"),
            "track_end": data[-1].get("t"),
            "race_window_start": start_time,
            "race_window_end": end_time,
        })
        boats.append(entry)

    return {"race_id": race_id, "boats": boats}


@router.get("/{race_id}/ais")
def get_race_ais(race_id: str, start: Optional[str] = None, end: Optional[str] = None):
    """Return non-participant AIS vessel tracks for the race map overlay."""
    doc = load_json_or_empty(f"races/{race_id}/ais/vessels.json")
    if not doc or not doc.get("vessels"):
        return {"vessels": [], "source": None}

    vessels = doc.get("vessels", [])
    if start and end:
        clipped = []
        for vessel in vessels:
            points = [p for p in vessel.get("positions", []) if _in_window(p.get("t", ""), start, end)]
            if points:
                row = {k: v for k, v in vessel.items() if k != "positions"}
                row["positions"] = points
                clipped.append(row)
        vessels = clipped

    return {
        "vessels": vessels,
        "source": doc.get("source"),
        "center": doc.get("center"),
        "radius_nm": doc.get("radius_nm"),
        "window": doc.get("window"),
        "generated_at": doc.get("generated_at"),
    }


# --- Session Matching -----------------------------------------------------

@router.post("/{race_id}/match-sessions")
def match_sessions_to_race(race_id: str, request: Request):
    """
    Auto-match E1-E6 device sessions to a race based on time overlap.

    Finds sessions from each device that overlap with the race time window
    and updates the race's boat session_path fields.
    """
    require_admin(request)
    race_data = get_race_dict(race_id)
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    race_start = race_data["start_time"]
    race_end = race_data["end_time"]
    race_date = race_data["date"]

    matched = []
    for boat in race_data.get("boats", []):
        device_id = boat["device_id"]

        # Find sessions for this device on race date
        try:
            sessions = _find_device_sessions(device_id, race_date)
        except Exception:
            sessions = []

        # Find session with best overlap
        best_session = None
        best_overlap = 0

        for session in sessions:
            session_start = session.get("start_time", "")
            session_end = session.get("end_time", "")

            # Calculate overlap
            overlap_start = max(race_start, session_start)
            overlap_end = min(race_end, session_end)

            if overlap_start < overlap_end:
                # There is overlap
                overlap_duration = geo.iso_diff_seconds(overlap_end, overlap_start)
                if overlap_duration > best_overlap:
                    best_overlap = overlap_duration
                    best_session = session

        if best_session:
            boat["session_path"] = best_session["session_path"]
            matched.append({
                "device_id": device_id,
                "session_path": best_session["session_path"],
                "overlap_sec": best_overlap,
            })
        else:
            matched.append({
                "device_id": device_id,
                "session_path": None,
                "error": "No overlapping session found",
            })

    # Save updated race
    race_data["updated_at"] = now_iso()
    save_race_dict(race_data)

    return {"race_id": race_id, "matched": matched}


@router.post("/{race_id}/boats/{device_id}/gpx")
async def upload_boat_gpx(
    race_id: str, device_id: str, request: Request, file: UploadFile = File(...)
):
    """Upload a GPX track file as the GPS source for a boat in a race."""
    require_admin(request)

    race_data = get_race_dict(race_id)
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    boat = next((b for b in race_data.get("boats", []) if b["device_id"] == device_id), None)
    if boat is None:
        raise HTTPException(404, f"Boat {device_id} not found in race {race_id}")

    content = await file.read()
    try:
        track_points = gpx.parse_gpx(content)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse GPX: {e}")

    if not track_points:
        raise HTTPException(400, "GPX file contains no track points")

    gpx_key = f"races/{race_id}/gpx/{device_id}.json"
    save_json(gpx_key, track_points)

    boat["gpx_path"] = gpx_key
    boat["session_path"] = None  # GPX replaces session
    race_data["updated_at"] = now_iso()
    save_race_dict(race_data)

    return {
        "device_id": device_id,
        "gpx_path": gpx_key,
        "points": len(track_points),
        "start_time": track_points[0]["t"],
        "end_time": track_points[-1]["t"],
    }


# --- Auto-Suggest Endpoints -----------------------------------------------

@router.post("/{race_id}/auto-start-line")
def auto_start_line(race_id: str, request: Request):
    """
    Estimate a start line from fleet positions at the gun time.

    Places the line perpendicular to the mean fleet heading, through the fleet
    centroid. Length scales to cover the fleet with 30m padding on each end.
    """
    require_admin(request)
    race_data = get_race_dict(race_id)
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    boat_gps = _load_race_gps(race_data)
    if not boat_gps:
        raise HTTPException(400, "No boat session data available for this race")

    try:
        return course.estimate_start_line(boat_gps, race_data["start_time"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{race_id}/suggest-marks")
def suggest_marks(race_id: str, request: Request):
    """
    Detect rounding points across boat tracks and cluster them into candidate marks.

    A rounding point is where a boat's course changes by >= 60° within a 30-second
    window. Points within 100m of each other are clustered; each cluster centroid
    becomes a suggested mark, ordered by the average time of the cluster.
    """
    require_admin(request)
    race_data = get_race_dict(race_id)
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    boat_gps = _load_race_gps(race_data)
    if not boat_gps:
        raise HTTPException(400, "No boat session data available for this race")

    return course.detect_marks(boat_gps)
