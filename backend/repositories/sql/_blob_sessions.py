"""Read-only blob session reader.

Sessions are derived from the per-session ``manifest.json`` files the processing
pipeline writes under ``{data_prefix}/{device}/{date}/``. The DB is the source of
truth (Phase 5); these helpers surface historical manifests not yet imported into
the table as **transient** ``SessionORM`` rows (attributes + ``to_dict`` work; the
session repo persists them via ``s.add`` when attributing/bootstrapping).
"""

from datetime import datetime
from typing import Optional

from ...db.models import SessionORM
from ...storage import BlobStore, BlobNotFound


def _duration(manifest: dict) -> int:
    duration_sec = manifest.get("duration_sec")
    if duration_sec:
        return int(duration_sec)
    start_time = manifest.get("start_time")
    end_time = manifest.get("end_time")
    if start_time and end_time:
        try:
            s = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            return int((e - s).total_seconds())
        except (ValueError, TypeError):
            return 0
    return 0


def _to_orm(manifest: dict, device_id: str, date: str) -> SessionORM:
    orm = SessionORM(device_id=device_id, date=date)
    orm.session_id = manifest.get("session_id")
    orm.start_time = manifest.get("start_time")
    orm.end_time = manifest.get("end_time")
    orm.duration_sec = _duration(manifest)
    orm.boat = manifest.get("boat")
    orm.name = manifest.get("name")
    orm.sensors = manifest.get("sensors") or []
    orm.has_video = manifest.get("has_video", False)
    orm.has_analysis = manifest.get("has_analysis", False)
    orm.trim = manifest.get("trim")
    orm.owner_user_id = manifest.get("owner_user_id")
    orm.boat_id = manifest.get("boat_id")
    orm.visibility = manifest.get("visibility") or "private"
    orm.club_id = manifest.get("club_id")
    orm.group_id = manifest.get("group_id")
    orm.regatta_id = manifest.get("regatta_id")
    orm.race_id = manifest.get("race_id")
    return orm


def list_blob_sessions(blob: BlobStore, data_prefix: str) -> list[SessionORM]:
    out = []
    for key in blob.list_keys(f"{data_prefix}/"):
        if not key.endswith("manifest.json"):
            continue
        try:
            manifest = blob.get_json(key)
            parts = key.split("/")
            device_id = parts[1] if len(parts) > 2 else "unknown"
            date = parts[2] if len(parts) > 2 else "unknown"
            if device_id == "manual":
                # Manual/GPX sessions live under processed/manual/{session.id}/
                # and are already DB rows (created directly, not via ingest) —
                # not a device+date pair to import.
                continue
            out.append(_to_orm(manifest, device_id, date))
        except Exception:
            continue
    return out


def get_blob_session(blob: BlobStore, data_prefix: str, device_id: str, date: str) -> Optional[SessionORM]:
    key = f"{data_prefix}/{device_id}/{date}/manifest.json"
    try:
        manifest = blob.get_json(key)
    except BlobNotFound:
        return None
    return _to_orm(manifest, device_id, date)
