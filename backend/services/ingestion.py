"""Ingestion core shared by the device API, manual imports, and system
callbacks: find-or-create of activity/session for a boat+timeframe, raw-key
layout, and worker dispatch.

Key layout (docs/device-protocol.md + api-project.md):
- ``raw/uploads/{session_upload_id}/{filename}`` — device bundles and copied
  CSV imports; each object PUT fires the storage webhook.
- ``raw/imports/{import_id}/{original_filename}`` — manual import staging
  (ignored by the webhook; processing is dispatched by /complete).
- ``processed/uploads/{session_upload_id}/{sensor}.json`` — worker output,
  referenced by ``session_streams.data_ref``.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import requests

from ..repositories import get_repos
from ..storage import get_blob_store
from . import wind_lookup

logger = logging.getLogger(__name__)

SESSION_MERGE_GAP_MINUTES = 10
UPLOAD_URL_EXPIRY_S = 3600


def bucket_name() -> str:
    return os.environ.get("SAILFRAMES_BUCKET", "sailframes-fleet-data-prod")


def upload_raw_key(session_upload_id: uuid.UUID, filename: str) -> str:
    return f"raw/uploads/{session_upload_id}/{filename}"


def import_raw_key(import_id: uuid.UUID, original_filename: str) -> str:
    return f"raw/imports/{import_id}/{original_filename}"


def processed_prefix(session_upload_id: uuid.UUID) -> str:
    return f"processed/uploads/{session_upload_id}/"


def find_or_create_session(*, boat_id: uuid.UUID, started_at: datetime,
                           ended_at: Optional[datetime] = None,
                           activity_id: Optional[uuid.UUID] = None,
                           created_by: Optional[uuid.UUID] = None):
    """The one session per boat per activity/timeframe.

    Explicit ``activity_id``: reuse that activity's session for the boat (or
    create it). Otherwise match an existing session of the boat within the
    merge gap and extend its window, else create a private solo activity +
    session (docs/er-project.md, ``activities`` note).
    """
    repos = get_repos()
    if activity_id is not None:
        # Sessions extend their own window above — the parent activity's
        # window must widen right along with it, since replay/data endpoints
        # (GET /activities/{id}/data) filter GPS points by the *activity's*
        # started_at/ended_at, not each session's.
        repos.activities.extend_window(activity_id, started_at, ended_at)
        for sess in repos.sessions.list(activity_id=activity_id, boat_id=boat_id):
            repos.sessions.extend_window(sess.id, started_at, ended_at)
            return repos.sessions.get(sess.id)
        return repos.sessions.create({
            "activity_id": activity_id, "boat_id": boat_id,
            "started_at": started_at, "ended_at": ended_at, "status": "pending",
        })

    sess = repos.sessions.find_for_boat_window(
        boat_id, started_at, ended_at, gap_minutes=SESSION_MERGE_GAP_MINUTES
    )
    if sess is not None:
        repos.sessions.extend_window(sess.id, started_at, ended_at)
        return repos.sessions.get(sess.id)

    activity = repos.activities.create({
        "type": "solo", "visibility": "private", "created_by": created_by,
        "started_at": started_at, "ended_at": ended_at,
    })
    return repos.sessions.create({
        "activity_id": activity.id, "boat_id": boat_id,
        "started_at": started_at, "ended_at": ended_at, "status": "pending",
    })


# --- worker dispatch ---------------------------------------------------------

def _worker_timeout() -> int:
    return int(os.environ.get("WORKER_TIMEOUT_SEC", "300"))


def dispatch_csv_key(bucket: str, key: str) -> None:
    """Send one S3-shaped record to the process_upload worker (Lambda RIE)."""
    url = os.environ.get("PROCESS_UPLOAD_URL")
    if not url:
        raise RuntimeError("PROCESS_UPLOAD_URL is not configured")
    record = {"s3": {"bucket": {"name": bucket}, "object": {"key": key}}}
    requests.post(url, json={"Records": [record]}, timeout=_worker_timeout())


def dispatch_analysis(bucket: str, prefix: str) -> None:
    """Ask the worker to (re)build analysis.json for a processed prefix.

    Best-effort: streams are already registered by this point, and this is
    reachable directly from a user click (``POST /sessions/{id}/reanalyze``),
    so a worker/network hiccup must not bubble up as a 500 to that click."""
    url = os.environ.get("PROCESS_UPLOAD_URL")
    if not url:
        return
    record = {"analyze": {"prefix": prefix}, "bucket": bucket}
    try:
        requests.post(url, json={"Records": [record]}, timeout=_worker_timeout())
    except requests.RequestException:
        logger.warning("analysis dispatch failed for prefix %s", prefix, exc_info=True)


def activity_thumbnail_prefixes(activity_id: uuid.UUID) -> list:
    """Each sibling session's most recently processed upload prefix — the
    inputs to the worker's overlay composite (``dispatch_activity_thumbnail``).
    Shared by the automatic post-analysis trigger (``system.py``) and the
    manual "regenerate" action (``routers/activities.py``)."""
    repos = get_repos()
    prefixes = []
    for session in repos.sessions.list(activity_id=activity_id):
        uploads = repos.ingest.list_uploads(session_id=session.id)
        if not uploads:
            continue
        latest = max(uploads, key=lambda u: u.uploaded_at)
        prefixes.append(processed_prefix(latest.id))
    return prefixes


def dispatch_activity_thumbnail(bucket: str, activity_id: uuid.UUID, prefixes: list) -> None:
    """Ask the worker to (re)composite an activity's overlay thumbnail from
    every session's processed prefix (see ``upsert_session_analysis``, which
    calls this after each session's own analysis lands).

    Best-effort like ``dispatch_analysis``, but unlike that one this is also
    reachable directly from a request (the manual "regenerate" action in
    ``routers/activities.py``), so a worker/network hiccup must not bubble up
    as a 500 to that click — log it and move on, the user can retry."""
    url = os.environ.get("PROCESS_UPLOAD_URL")
    if not url:
        return
    record = {"activity_thumbnail": {"activity_id": str(activity_id), "prefixes": prefixes},
              "bucket": bucket}
    try:
        requests.post(url, json={"Records": [record]}, timeout=_worker_timeout())
    except requests.RequestException:
        logger.warning("activity thumbnail dispatch failed for %s", activity_id, exc_info=True)


def write_wind_cache(prefix: str, lat: float, lng: float,
                     start: datetime, end: datetime) -> None:
    """Pre-fetch the region's wind for a session's time window and drop it in
    the processed prefix as ``wind_cache.json``, so the (DB-blind) worker can
    use it as the true-wind source when the session has no onboard wind sensor.

    Best-effort: resolving the station triggers a historical backfill when the
    cache is empty for an old date (see ``wind_lookup.observations_in_window``).
    A failure here just means the worker falls back to GPS-estimated wind."""
    try:
        _, rows = wind_lookup.observations_in_window(lat, lng, start, end)
        # Only the fields the worker needs, as JSON primitives — the blob store's
        # put_json uses plain json.dumps (no UUID/datetime encoder like FastAPI).
        payload = [{
            "observed_at": o.observed_at.isoformat(),
            "twd_deg": o.twd_deg,
            "tws_kts": o.tws_kts,
            "gust_kts": o.gust_kts,
        } for o in rows]
        get_blob_store().put_json(f"{prefix}wind_cache.json", payload)
    except Exception:
        logger.warning("wind cache pre-fetch failed for prefix %s", prefix, exc_info=True)
