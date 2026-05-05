"""Race and Regatta API endpoints for SailFrames.

Provides CRUD operations for races and regattas, multi-boat data loading,
and session matching functionality.
"""

import json
import math
import os
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import boto3
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from .auth import require_admin

router = APIRouter(prefix="/api", tags=["races"])

# Configuration (shared with main.py)
S3_BUCKET = os.environ.get("SAILFRAMES_BUCKET", "sailframes-fleet-data-prod")
LOCAL_DATA_DIR = os.environ.get("SAILFRAMES_LOCAL_DATA", None)

s3 = boto3.client("s3") if not LOCAL_DATA_DIR else None

# S3 paths for race data
RACES_INDEX_KEY = "races/races.json"
REGATTAS_INDEX_KEY = "regattas/regattas.json"
RACEDAYS_INDEX_KEY = "racedays/racedays.json"


# --- Pydantic Models for Request/Response ---

class StartFinishLineModel(BaseModel):
    pin_lat: float
    pin_lon: float
    boat_lat: float
    boat_lon: float


class MarkModel(BaseModel):
    mark_id: str
    name: str = ""
    mark_type: str = "custom"  # windward|leeward|gate_port|gate_stbd|offset|custom
    lat: float
    lon: float


class RaceBoatModel(BaseModel):
    device_id: str
    boat_name: str
    sail_number: str = ""
    session_path: Optional[str] = None
    gpx_path: Optional[str] = None  # Set after GPX track upload


class RaceCreateModel(BaseModel):
    name: str
    date: str  # YYYY-MM-DD
    start_time: str  # ISO timestamp
    end_time: str  # ISO timestamp
    regatta_id: Optional[str] = None
    raceday_id: Optional[str] = None
    boats: list[RaceBoatModel] = []
    start_line: Optional[StartFinishLineModel] = None
    finish_line: Optional[StartFinishLineModel] = None
    marks: list[MarkModel] = []
    course: list[str] = []
    finish_order: list[str] = []


class RaceUpdateModel(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    boats: Optional[list[RaceBoatModel]] = None
    start_line: Optional[StartFinishLineModel] = None
    finish_line: Optional[StartFinishLineModel] = None
    marks: Optional[list[MarkModel]] = None
    course: Optional[list[str]] = None
    finish_order: Optional[list[str]] = None
    raceday_id: Optional[str] = None


class RaceDayCreateModel(BaseModel):
    date: str  # YYYY-MM-DD
    type: str = "race_day"  # "race_day" | "training_day"
    name: Optional[str] = None
    regatta_id: Optional[str] = None


class RaceDayUpdateModel(BaseModel):
    date: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    regatta_id: Optional[str] = None


class RegattaCreateModel(BaseModel):
    name: str
    venue: str
    boat_class: str
    start_date: str
    end_date: str


class RegattaUpdateModel(BaseModel):
    name: Optional[str] = None
    venue: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# --- Helper Functions ---

def _load_json(key: str) -> dict:
    """Load JSON from S3 or local filesystem."""
    if LOCAL_DATA_DIR:
        path = Path(LOCAL_DATA_DIR) / key
        if not path.exists():
            return {}
        return json.loads(path.read_text())
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(resp["Body"].read())
    except s3.exceptions.NoSuchKey:
        return {}
    except Exception:
        return {}


def _save_json(key: str, data: dict):
    """Save JSON to S3 or local filesystem."""
    if LOCAL_DATA_DIR:
        path = Path(LOCAL_DATA_DIR) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    else:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType="application/json",
        )


def _delete_json(key: str):
    """Delete JSON from S3 or local filesystem."""
    if LOCAL_DATA_DIR:
        path = Path(LOCAL_DATA_DIR) / key
        if path.exists():
            path.unlink()
    else:
        try:
            s3.delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception:
            pass


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def _load_races_index() -> dict:
    """Load races index (list of all races)."""
    data = _load_json(RACES_INDEX_KEY)
    if not data:
        return {"races": []}
    return data


def _save_races_index(data: dict):
    """Save races index."""
    _save_json(RACES_INDEX_KEY, data)


def _load_regattas_index() -> dict:
    """Load regattas index."""
    data = _load_json(REGATTAS_INDEX_KEY)
    if not data:
        return {"regattas": []}
    return data


def _save_regattas_index(data: dict):
    """Save regattas index."""
    _save_json(REGATTAS_INDEX_KEY, data)


def _load_racedays_index() -> dict:
    data = _load_json(RACEDAYS_INDEX_KEY)
    if not data:
        return {"race_days": []}
    return data


def _save_racedays_index(data: dict):
    _save_json(RACEDAYS_INDEX_KEY, data)


# --- Regatta Endpoints ---

@router.get("/regattas")
def list_regattas():
    """List all regattas."""
    index = _load_regattas_index()
    return {"regattas": index.get("regattas", [])}


@router.get("/regattas/{regatta_id}")
def get_regatta(regatta_id: str):
    """Get a regatta with its races."""
    index = _load_regattas_index()
    for regatta in index.get("regattas", []):
        if regatta["regatta_id"] == regatta_id:
            # Load races for this regatta
            races_index = _load_races_index()
            regatta_races = [
                r for r in races_index.get("races", [])
                if r.get("regatta_id") == regatta_id
            ]
            return {**regatta, "races": regatta_races}
    raise HTTPException(404, f"Regatta not found: {regatta_id}")


@router.post("/regattas")
def create_regatta(regatta: RegattaCreateModel, request: Request):
    """Create a new regatta."""
    require_admin(request)
    regatta_id = str(uuid.uuid4())[:8]
    now = _now_iso()

    new_regatta = {
        "regatta_id": regatta_id,
        "name": regatta.name,
        "venue": regatta.venue,
        "boat_class": regatta.boat_class,
        "start_date": regatta.start_date,
        "end_date": regatta.end_date,
        "race_ids": [],
        "created_at": now,
        "updated_at": now,
    }

    index = _load_regattas_index()
    index["regattas"].append(new_regatta)
    _save_regattas_index(index)

    return new_regatta


@router.patch("/regattas/{regatta_id}")
def update_regatta(regatta_id: str, update: RegattaUpdateModel, request: Request):
    """Update a regatta."""
    require_admin(request)
    index = _load_regattas_index()
    for i, regatta in enumerate(index.get("regattas", [])):
        if regatta["regatta_id"] == regatta_id:
            if update.name is not None:
                regatta["name"] = update.name
            if update.venue is not None:
                regatta["venue"] = update.venue
            if update.start_date is not None:
                regatta["start_date"] = update.start_date
            if update.end_date is not None:
                regatta["end_date"] = update.end_date
            regatta["updated_at"] = _now_iso()
            index["regattas"][i] = regatta
            _save_regattas_index(index)
            return regatta
    raise HTTPException(404, f"Regatta not found: {regatta_id}")


@router.delete("/regattas/{regatta_id}")
def delete_regatta(regatta_id: str, request: Request):
    """Delete a regatta (does not delete races)."""
    require_admin(request)
    index = _load_regattas_index()
    original_len = len(index.get("regattas", []))
    index["regattas"] = [r for r in index["regattas"] if r["regatta_id"] != regatta_id]
    if len(index["regattas"]) == original_len:
        raise HTTPException(404, f"Regatta not found: {regatta_id}")
    _save_regattas_index(index)
    return {"deleted": regatta_id}


# --- Race Day Endpoints ---

@router.get("/racedays")
def list_racedays(regatta_id: Optional[str] = None):
    index = _load_racedays_index()
    days = index.get("race_days", [])
    if regatta_id:
        days = [d for d in days if d.get("regatta_id") == regatta_id]
    return {"race_days": sorted(days, key=lambda d: d.get("date", ""))}


@router.get("/racedays/{raceday_id}")
def get_raceday(raceday_id: str):
    index = _load_racedays_index()
    for day in index.get("race_days", []):
        if day["raceday_id"] == raceday_id:
            return day
    raise HTTPException(404, f"Race day not found: {raceday_id}")


@router.post("/racedays")
def create_raceday(raceday: RaceDayCreateModel, request: Request):
    require_admin(request)
    raceday_id = str(uuid.uuid4())[:8]
    now = _now_iso()

    new_day = {
        "raceday_id": raceday_id,
        "date": raceday.date,
        "type": raceday.type,
        "name": raceday.name or None,
        "regatta_id": raceday.regatta_id or None,
        "race_ids": [],
        "created_at": now,
        "updated_at": now,
    }

    index = _load_racedays_index()
    index["race_days"].append(new_day)
    _save_racedays_index(index)

    return new_day


@router.patch("/racedays/{raceday_id}")
def update_raceday(raceday_id: str, update: RaceDayUpdateModel, request: Request):
    require_admin(request)
    index = _load_racedays_index()
    for i, day in enumerate(index.get("race_days", [])):
        if day["raceday_id"] == raceday_id:
            if update.date is not None:
                day["date"] = update.date
            if update.type is not None:
                day["type"] = update.type
            if update.name is not None:
                day["name"] = update.name or None
            if update.regatta_id is not None:
                day["regatta_id"] = update.regatta_id or None
            day["updated_at"] = _now_iso()
            index["race_days"][i] = day
            _save_racedays_index(index)
            return day
    raise HTTPException(404, f"Race day not found: {raceday_id}")


@router.delete("/racedays/{raceday_id}")
def delete_raceday(raceday_id: str, request: Request):
    require_admin(request)
    index = _load_racedays_index()
    original_len = len(index.get("race_days", []))
    index["race_days"] = [d for d in index["race_days"] if d["raceday_id"] != raceday_id]
    if len(index["race_days"]) == original_len:
        raise HTTPException(404, f"Race day not found: {raceday_id}")
    _save_racedays_index(index)
    return {"deleted": raceday_id}


# --- Race Endpoints ---

@router.get("/races")
def list_races(regatta_id: Optional[str] = None, date: Optional[str] = None, raceday_id: Optional[str] = None):
    """List all races, optionally filtered by regatta, date, or race day."""
    index = _load_races_index()
    races = index.get("races", [])

    if regatta_id:
        races = [r for r in races if r.get("regatta_id") == regatta_id]
    if date:
        races = [r for r in races if r.get("date") == date]
    if raceday_id:
        races = [r for r in races if r.get("raceday_id") == raceday_id]

    return {"races": sorted(races, key=lambda r: (r.get("date", ""), r.get("start_time", "")))}


@router.get("/races/{race_id}")
def get_race(race_id: str):
    """Get a single race by ID."""
    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")
    return race_data


@router.post("/races")
def create_race(race: RaceCreateModel, request: Request):
    """Create a new race."""
    require_admin(request)
    race_id = str(uuid.uuid4())[:8]
    now = _now_iso()

    new_race = {
        "race_id": race_id,
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
    }

    # Save race definition
    _save_json(f"races/{race_id}/race.json", new_race)

    # Update races index
    index = _load_races_index()
    index["races"].append({
        "race_id": race_id,
        "name": race.name,
        "date": race.date,
        "start_time": race.start_time,
        "end_time": race.end_time,
        "regatta_id": race.regatta_id,
        "raceday_id": race.raceday_id,
        "boat_count": len(race.boats),
    })
    _save_races_index(index)

    # Update race day's race_ids if linked
    if race.raceday_id:
        racedays_index = _load_racedays_index()
        for raceday in racedays_index.get("race_days", []):
            if raceday["raceday_id"] == race.raceday_id:
                if race_id not in raceday.get("race_ids", []):
                    raceday.setdefault("race_ids", []).append(race_id)
                    raceday["updated_at"] = now
                break
        _save_racedays_index(racedays_index)

    # Update regatta's race_ids if linked
    if race.regatta_id:
        regattas_index = _load_regattas_index()
        for regatta in regattas_index.get("regattas", []):
            if regatta["regatta_id"] == race.regatta_id:
                if race_id not in regatta.get("race_ids", []):
                    regatta.setdefault("race_ids", []).append(race_id)
                    regatta["updated_at"] = now
                break
        _save_regattas_index(regattas_index)

    return new_race


@router.patch("/races/{race_id}")
def update_race(race_id: str, update: RaceUpdateModel, request: Request):
    """Update a race."""
    require_admin(request)
    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    if update.name is not None:
        race_data["name"] = update.name
    if update.start_time is not None:
        race_data["start_time"] = update.start_time
    if update.end_time is not None:
        race_data["end_time"] = update.end_time
    if update.boats is not None:
        race_data["boats"] = [b.model_dump() for b in update.boats]
    if update.start_line is not None:
        race_data["start_line"] = update.start_line.model_dump()
    if update.finish_line is not None:
        race_data["finish_line"] = update.finish_line.model_dump()
    if update.marks is not None:
        race_data["marks"] = [m.model_dump() for m in update.marks]
    if update.course is not None:
        race_data["course"] = update.course
    if update.finish_order is not None:
        race_data["finish_order"] = update.finish_order
    if update.raceday_id is not None:
        race_data["raceday_id"] = update.raceday_id or None

    race_data["updated_at"] = _now_iso()
    _save_json(f"races/{race_id}/race.json", race_data)

    # Update index
    index = _load_races_index()
    for i, r in enumerate(index.get("races", [])):
        if r["race_id"] == race_id:
            index["races"][i]["name"] = race_data["name"]
            index["races"][i]["start_time"] = race_data["start_time"]
            index["races"][i]["end_time"] = race_data["end_time"]
            index["races"][i]["raceday_id"] = race_data.get("raceday_id")
            index["races"][i]["boat_count"] = len(race_data.get("boats", []))
            break
    _save_races_index(index)

    return race_data


@router.delete("/races/{race_id}")
def delete_race(race_id: str, request: Request):
    """Delete a race."""
    require_admin(request)
    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    # Delete race files
    _delete_json(f"races/{race_id}/race.json")
    _delete_json(f"races/{race_id}/results.json")

    # Update index
    index = _load_races_index()
    index["races"] = [r for r in index["races"] if r["race_id"] != race_id]
    _save_races_index(index)

    # Update regatta if linked
    if race_data.get("regatta_id"):
        regattas_index = _load_regattas_index()
        for regatta in regattas_index.get("regattas", []):
            if regatta["regatta_id"] == race_data["regatta_id"]:
                regatta["race_ids"] = [rid for rid in regatta.get("race_ids", []) if rid != race_id]
                regatta["updated_at"] = _now_iso()
                break
        _save_regattas_index(regattas_index)

    return {"deleted": race_id}


# --- Multi-Boat Data Endpoint ---

@router.get("/races/{race_id}/data")
def get_race_data(
    race_id: str,
    sensors: str = Query("gps,imu,wind", description="Comma-separated sensors to load"),
):
    """
    Load time-aligned sensor data for all boats in a race.

    Returns data filtered to race time window for each boat that has
    a matched session.
    """
    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    start_time = race_data["start_time"]
    end_time = race_data["end_time"]
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
                    data = _load_json(gpx_path)
                    if isinstance(data, list):
                        filtered = [
                            d for d in data
                            if start_time <= d.get("t", "") <= end_time
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
                data = _load_json(sensor_key)
                if isinstance(data, list):
                    filtered = [
                        d for d in data
                        if start_time <= d.get("t", "") <= end_time
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


# --- Session Matching ---

@router.post("/races/{race_id}/match-sessions")
def match_sessions_to_race(race_id: str, request: Request):
    """
    Auto-match E1-E6 device sessions to a race based on time overlap.

    Finds sessions from each device that overlap with the race time window
    and updates the race's boat session_path fields.
    """
    require_admin(request)
    race_data = _load_json(f"races/{race_id}/race.json")
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
                overlap_duration = _iso_diff_seconds(overlap_end, overlap_start)
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
    race_data["updated_at"] = _now_iso()
    _save_json(f"races/{race_id}/race.json", race_data)

    return {"race_id": race_id, "matched": matched}


@router.post("/races/{race_id}/boats/{device_id}/gpx")
async def upload_boat_gpx(
    race_id: str, device_id: str, request: Request, file: UploadFile = File(...)
):
    """Upload a GPX track file as the GPS source for a boat in a race."""
    require_admin(request)

    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    boat = next((b for b in race_data.get("boats", []) if b["device_id"] == device_id), None)
    if boat is None:
        raise HTTPException(404, f"Boat {device_id} not found in race {race_id}")

    content = await file.read()
    try:
        track_points = _parse_gpx(content)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse GPX: {e}")

    if not track_points:
        raise HTTPException(400, "GPX file contains no track points")

    gpx_key = f"races/{race_id}/gpx/{device_id}.json"
    _save_json(gpx_key, track_points)

    boat["gpx_path"] = gpx_key
    boat["session_path"] = None  # GPX replaces session
    race_data["updated_at"] = _now_iso()
    _save_json(f"races/{race_id}/race.json", race_data)

    return {
        "device_id": device_id,
        "gpx_path": gpx_key,
        "points": len(track_points),
        "start_time": track_points[0]["t"],
        "end_time": track_points[-1]["t"],
    }


def _find_device_sessions(device_id: str, date: str) -> list[dict]:
    """Find all sessions for a device on a given date."""
    sessions = []

    # Look for manifest files in processed folder
    prefix = f"processed/{device_id}/{date}"

    if LOCAL_DATA_DIR:
        base = Path(LOCAL_DATA_DIR) / prefix
        if base.exists():
            for manifest_path in base.glob("*/manifest.json"):
                try:
                    manifest = json.loads(manifest_path.read_text())
                    session_path = manifest_path.parent.name
                    sessions.append({
                        "session_path": f"{date}/{session_path}" if "/" not in session_path else session_path,
                        "start_time": manifest.get("start_time", ""),
                        "end_time": manifest.get("end_time", ""),
                    })
                except Exception:
                    pass
    else:
        # List S3 objects
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if obj["Key"].endswith("/manifest.json"):
                        try:
                            resp = s3.get_object(Bucket=S3_BUCKET, Key=obj["Key"])
                            manifest = json.loads(resp["Body"].read())
                            # Extract session path from key
                            parts = obj["Key"].split("/")
                            session_folder = parts[-2]
                            sessions.append({
                                "session_path": f"{date}/{session_folder}",
                                "start_time": manifest.get("start_time", ""),
                                "end_time": manifest.get("end_time", ""),
                            })
                        except Exception:
                            pass
        except Exception:
            pass

    return sessions


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _parse_gpx(content: bytes) -> list[dict]:
    """Parse GPX XML into GPS track points matching processed gps.json format."""
    root = ET.fromstring(content)
    ns_match = re.match(r'\{([^}]+)\}', root.tag)
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
                dt = _iso_diff_seconds(pt["t"], prev["t"])
                if dt > 0:
                    dist_m = _haversine_m(prev["lat"], prev["lon"], pt["lat"], pt["lon"])
                    sog = (dist_m / dt) * 1.94384
            except Exception:
                pass

        if i > 0:
            prev = raw[i - 1]
            cog = _bearing(prev["lat"], prev["lon"], pt["lat"], pt["lon"])
        elif i < len(raw) - 1:
            nxt = raw[i + 1]
            cog = _bearing(pt["lat"], pt["lon"], nxt["lat"], nxt["lon"])

        result.append({
            "t": pt["t"],
            "lat": pt["lat"],
            "lon": pt["lon"],
            "speed_kn": round(sog, 2),
            "course": round(cog, 1),
        })

    return result


def _iso_diff_seconds(end: str, start: str) -> float:
    """Calculate difference in seconds between two ISO timestamps."""
    try:
        from datetime import datetime
        fmt = "%Y-%m-%dT%H:%M:%S"
        # Handle fractional seconds and Z suffix
        start_clean = start.replace("Z", "").split(".")[0]
        end_clean = end.replace("Z", "").split(".")[0]
        start_dt = datetime.strptime(start_clean, fmt)
        end_dt = datetime.strptime(end_clean, fmt)
        return (end_dt - start_dt).total_seconds()
    except Exception:
        return 0


# --- Course Auto-Suggest Helpers ---

import math


def _meters_per_deg_lat() -> float:
    return 111320.0


def _meters_per_deg_lon(lat: float) -> float:
    return 111320.0 * math.cos(math.radians(lat))


def _offset_meters(lat: float, lon: float, bearing_deg: float, dist_m: float) -> tuple[float, float]:
    """Return (lat, lon) offset from given point by bearing+distance, flat-earth approx."""
    dx = dist_m * math.sin(math.radians(bearing_deg))
    dy = dist_m * math.cos(math.radians(bearing_deg))
    dlat = dy / _meters_per_deg_lat()
    dlon = dx / _meters_per_deg_lon(lat)
    return lat + dlat, lon + dlon


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    R = 6371000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _mean_angle_deg(angles: list[float]) -> float:
    """Circular mean of angles in degrees."""
    if not angles:
        return 0.0
    xs = sum(math.cos(math.radians(a)) for a in angles)
    ys = sum(math.sin(math.radians(a)) for a in angles)
    return (math.degrees(math.atan2(ys, xs)) + 360.0) % 360.0


def _angle_diff_deg(a: float, b: float) -> float:
    """Smallest signed difference a-b, in degrees, in [-180, 180]."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return d


def _load_race_gps(race_data: dict) -> dict:
    """Return {device_id: [gps_points]} for all boats with session data, filtered to race window."""
    start_time = race_data["start_time"]
    end_time = race_data["end_time"]
    out = {}
    for boat in race_data.get("boats", []):
        device_id = boat["device_id"]
        session_path = boat.get("session_path")
        if not session_path:
            continue
        key = f"processed/{device_id}/{session_path}/gps.json"
        data = _load_json(key)
        if not isinstance(data, list):
            continue
        filtered = [d for d in data if start_time <= d.get("t", "") <= end_time]
        if filtered:
            out[device_id] = filtered
    return out


def _points_near(points: list[dict], iso_target: str, window_sec: float = 30.0) -> list[dict]:
    """Return points within window_sec of iso_target."""
    out = []
    for p in points:
        t = p.get("t", "")
        if not t:
            continue
        d = abs(_iso_diff_seconds(t, iso_target))
        if d <= window_sec:
            out.append(p)
    return out


# --- Auto-Suggest Endpoints ---

@router.post("/races/{race_id}/auto-start-line")
def auto_start_line(race_id: str, request: Request):
    """
    Estimate a start line from fleet positions at the gun time.

    Places the line perpendicular to the mean fleet heading, through the fleet
    centroid. Length scales to cover the fleet with 30m padding on each end.
    """
    require_admin(request)
    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    boat_gps = _load_race_gps(race_data)
    if not boat_gps:
        raise HTTPException(400, "No boat session data available for this race")

    # Gather position + heading for each boat at start_time
    start_iso = race_data["start_time"]
    positions = []
    headings = []
    for device_id, gps in boat_gps.items():
        near = _points_near(gps, start_iso, window_sec=30.0)
        if not near:
            continue
        # Closest to start
        closest = min(near, key=lambda p: abs(_iso_diff_seconds(p.get("t", ""), start_iso)))
        lat, lon = closest.get("lat"), closest.get("lon")
        if lat is None or lon is None:
            continue
        positions.append((lat, lon))
        cog = closest.get("course")
        if cog is not None:
            headings.append(cog)

    if len(positions) < 1:
        raise HTTPException(400, "No boat positions available at start time")

    # Centroid
    clat = sum(p[0] for p in positions) / len(positions)
    clon = sum(p[1] for p in positions) / len(positions)

    # Mean heading, fallback to north if unknown
    mean_heading = _mean_angle_deg(headings) if headings else 0.0

    # Line perpendicular to heading
    perp = (mean_heading + 90.0) % 360.0

    # Length: fleet spread along perpendicular + 30m padding each side
    if len(positions) >= 2:
        # Project each point onto the perpendicular axis to measure spread
        projs = []
        for lat, lon in positions:
            dx_m = (lon - clon) * _meters_per_deg_lon(clat)
            dy_m = (lat - clat) * _meters_per_deg_lat()
            # Component along perp direction (sin/cos of perp)
            proj = dx_m * math.sin(math.radians(perp)) + dy_m * math.cos(math.radians(perp))
            projs.append(proj)
        half_len = max(abs(min(projs)), abs(max(projs))) + 30.0
    else:
        half_len = 40.0

    # Pin = perp direction, boat = opposite
    pin_lat, pin_lon = _offset_meters(clat, clon, perp, half_len)
    boat_lat, boat_lon = _offset_meters(clat, clon, (perp + 180.0) % 360.0, half_len)

    return {
        "start_line": {
            "pin_lat": pin_lat,
            "pin_lon": pin_lon,
            "boat_lat": boat_lat,
            "boat_lon": boat_lon,
        },
        "mean_heading_deg": mean_heading,
        "boats_used": len(positions),
    }


@router.post("/races/{race_id}/suggest-marks")
def suggest_marks(race_id: str, request: Request):
    """
    Detect rounding points across boat tracks and cluster them into candidate marks.

    A rounding point is where a boat's course changes by >= 60° within a 30-second
    window. Points within 100m of each other are clustered; each cluster centroid
    becomes a suggested mark, ordered by the average time of the cluster.
    """
    require_admin(request)
    race_data = _load_json(f"races/{race_id}/race.json")
    if not race_data:
        raise HTTPException(404, f"Race not found: {race_id}")

    boat_gps = _load_race_gps(race_data)
    if not boat_gps:
        raise HTTPException(400, "No boat session data available for this race")

    COURSE_CHANGE_DEG = 60.0
    WINDOW_SEC = 30.0
    CLUSTER_RADIUS_M = 100.0

    # Detect rounding points across all boats
    roundings = []  # list of {lat, lon, t, device_id}
    for device_id, gps in boat_gps.items():
        pts = [p for p in gps if p.get("lat") is not None and p.get("course") is not None]
        if len(pts) < 10:
            continue
        i = 0
        while i < len(pts):
            p = pts[i]
            t_i = p.get("t", "")
            cog_i = p["course"]
            # Find furthest point within WINDOW_SEC
            j = i + 1
            max_diff = 0.0
            max_j = i
            while j < len(pts):
                t_j = pts[j].get("t", "")
                if not t_j or _iso_diff_seconds(t_j, t_i) > WINDOW_SEC:
                    break
                diff = abs(_angle_diff_deg(pts[j]["course"], cog_i))
                if diff > max_diff:
                    max_diff = diff
                    max_j = j
                j += 1
            if max_diff >= COURSE_CHANGE_DEG:
                # Midpoint of i..max_j is the rounding location
                mid = pts[(i + max_j) // 2]
                roundings.append({
                    "lat": mid["lat"],
                    "lon": mid["lon"],
                    "t": mid.get("t", ""),
                    "device_id": device_id,
                })
                # Skip past this rounding
                i = max_j + 1
            else:
                i += 1

    if not roundings:
        return {"marks": [], "roundings_found": 0}

    # Cluster by distance (simple greedy single-linkage)
    clusters = []
    for r in roundings:
        placed = False
        for c in clusters:
            # Distance to cluster centroid
            d = _haversine_m(r["lat"], r["lon"], c["centroid_lat"], c["centroid_lon"])
            if d <= CLUSTER_RADIUS_M:
                c["points"].append(r)
                # Update centroid
                n = len(c["points"])
                c["centroid_lat"] = sum(p["lat"] for p in c["points"]) / n
                c["centroid_lon"] = sum(p["lon"] for p in c["points"]) / n
                placed = True
                break
        if not placed:
            clusters.append({
                "centroid_lat": r["lat"],
                "centroid_lon": r["lon"],
                "points": [r],
            })

    # Filter weak clusters (at least 2 boats or 2 roundings)
    clusters = [c for c in clusters if len(c["points"]) >= 2]

    # Sort clusters by average rounding time
    def avg_time(c):
        times = [p["t"] for p in c["points"] if p["t"]]
        if not times:
            return ""
        return sorted(times)[len(times) // 2]

    clusters.sort(key=avg_time)

    # Build mark suggestions
    suggested = []
    for i, c in enumerate(clusters):
        suggested.append({
            "mark_id": f"sug_{i+1}",
            "name": f"Mark {i + 1}",
            "mark_type": "windward" if i % 2 == 0 else "leeward",
            "lat": c["centroid_lat"],
            "lon": c["centroid_lon"],
            "rounding_count": len(c["points"]),
        })

    return {
        "marks": suggested,
        "roundings_found": len(roundings),
        "clusters_found": len(clusters),
    }
