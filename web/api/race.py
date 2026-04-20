"""Race and Regatta API endpoints for SailFrames.

Provides CRUD operations for races and regattas, multi-boat data loading,
and session matching functionality.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from fastapi import APIRouter, HTTPException, Query, Request
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


# --- Pydantic Models for Request/Response ---

class StartFinishLineModel(BaseModel):
    pin_lat: float
    pin_lon: float
    boat_lat: float
    boat_lon: float


class RaceBoatModel(BaseModel):
    device_id: str
    boat_name: str
    sail_number: str = ""
    session_path: Optional[str] = None


class RaceCreateModel(BaseModel):
    name: str
    date: str  # YYYY-MM-DD
    start_time: str  # ISO timestamp
    end_time: str  # ISO timestamp
    regatta_id: Optional[str] = None
    boats: list[RaceBoatModel] = []
    start_line: Optional[StartFinishLineModel] = None
    finish_line: Optional[StartFinishLineModel] = None
    finish_order: list[str] = []


class RaceUpdateModel(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    boats: Optional[list[RaceBoatModel]] = None
    start_line: Optional[StartFinishLineModel] = None
    finish_line: Optional[StartFinishLineModel] = None
    finish_order: Optional[list[str]] = None


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


# --- Race Endpoints ---

@router.get("/races")
def list_races(regatta_id: Optional[str] = None, date: Optional[str] = None):
    """List all races, optionally filtered by regatta or date."""
    index = _load_races_index()
    races = index.get("races", [])

    if regatta_id:
        races = [r for r in races if r.get("regatta_id") == regatta_id]
    if date:
        races = [r for r in races if r.get("date") == date]

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
        "boats": [b.model_dump() for b in race.boats],
        "start_line": race.start_line.model_dump() if race.start_line else None,
        "finish_line": race.finish_line.model_dump() if race.finish_line else None,
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
        "boat_count": len(race.boats),
    })
    _save_races_index(index)

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
    if update.finish_order is not None:
        race_data["finish_order"] = update.finish_order

    race_data["updated_at"] = _now_iso()
    _save_json(f"races/{race_id}/race.json", race_data)

    # Update index
    index = _load_races_index()
    for i, r in enumerate(index.get("races", [])):
        if r["race_id"] == race_id:
            index["races"][i]["name"] = race_data["name"]
            index["races"][i]["start_time"] = race_data["start_time"]
            index["races"][i]["end_time"] = race_data["end_time"]
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

        if not session_path:
            boats_data[device_id] = {"error": "No session matched", "boat": boat}
            continue

        boat_sensors = {}
        for sensor in requested_sensors:
            try:
                sensor_key = f"processed/{device_id}/{session_path}/{sensor}.json"
                data = _load_json(sensor_key)
                if isinstance(data, list):
                    # Filter to race time window
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
