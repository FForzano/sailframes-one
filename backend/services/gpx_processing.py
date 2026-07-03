"""Manual-session GPX processing (runs as a ``BackgroundTasks`` job — see
``routers/sessions.py::complete_gpx_upload``).

Parses the uploaded track, writes ``processed/manual/{id}/gps.json`` +
``manifest.json`` (same shape the CSV ingest pipeline produces for
device-sourced sessions, so ``routers/analysis.py``/``routers/data.py`` don't
need to know the difference), then dispatches the analysis step to the
``process_upload`` worker over HTTP.

Analysis (maneuvers/legs/polar/VMG) is *not* run in-process here: that worker
image carries numpy/pandas/``processing/*`` and the API container deliberately
doesn't (see ``deploy/Dockerfile.backend`` — "no processing pipeline, those are
their own containers"). We reuse the same Lambda-RIE HTTP dispatch
``routers/ingest.py`` already uses for CSV uploads, with a small event shape
(``{"analyze": {"prefix": ...}}``) the worker's ``lambda_handler`` recognizes
alongside its usual S3-event records (see ``workers/process_upload/handler.py``).
"""

import logging
import os

import requests

from . import gpx
from ..storage import get_blob_store, BlobNotFound
from ..repositories import get_repos

logger = logging.getLogger(__name__)

DATA_PREFIX = os.environ.get("SAILFRAMES_DATA_PREFIX", "processed")
BUCKET = os.environ.get("SAILFRAMES_BUCKET", "sailframes-fleet-data-prod")
PROCESS_UPLOAD_URL = os.environ.get("PROCESS_UPLOAD_URL")
WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT_SEC", "300"))


def _dispatch_analysis(prefix: str) -> bool:
    """POST the analyze-this-prefix event to the process_upload worker.
    Returns whether analysis.json was (as far as we can tell) produced."""
    if not PROCESS_UPLOAD_URL:
        logger.warning("PROCESS_UPLOAD_URL not configured — skipping analysis for %s", prefix)
        return False
    resp = requests.post(
        PROCESS_UPLOAD_URL,
        json={"Records": [{"analyze": {"prefix": prefix}, "bucket": BUCKET}]},
        timeout=WORKER_TIMEOUT,
    )
    resp.raise_for_status()
    return True


def process_manual_session_gpx(session_id: int) -> None:
    blob = get_blob_store()
    repos = get_repos()

    raw_key = f"raw/manual/{session_id}/track.gpx"
    prefix = f"{DATA_PREFIX}/manual/{session_id}/"

    try:
        content = blob.get_bytes(raw_key)
    except BlobNotFound:
        repos.sessions.set_processing_status(session_id, "failed", "GPX file not found")
        return

    try:
        points = gpx.parse_gpx(content)
    except Exception as exc:
        logger.exception("GPX parse failed for manual session %s", session_id)
        repos.sessions.set_processing_status(session_id, "failed", f"Could not parse GPX file: {exc}")
        return

    if not points:
        repos.sessions.set_processing_status(session_id, "failed", "GPX file contains no track points")
        return

    times = [p["t"] for p in points]
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    start_time, end_time = min(times), max(times)
    duration_sec = int(max(gpx.geo.iso_diff_seconds(end_time, start_time), 0))
    sensors = {"gps": {"samples": len(points), "start_time": start_time, "end_time": end_time}}
    manifest = {
        "device_id": "manual",
        "date": str(session_id),
        "session_id": None,
        "sensors": sensors,
        "start_time": start_time,
        "end_time": end_time,
        "duration_sec": duration_sec,
        "track_bounds": {
            "north": max(lats), "south": min(lats), "east": max(lons), "west": min(lons),
        },
        "has_analysis": False,
    }

    blob.put_json(f"{prefix}gps.json", points)
    blob.put_json(f"{prefix}manifest.json", manifest)

    has_analysis = False
    error = None
    try:
        has_analysis = _dispatch_analysis(prefix)
    except Exception as exc:
        logger.exception("Analysis dispatch failed for manual session %s", session_id)
        error = f"Track saved, but analysis could not be computed: {exc}"

    repos.sessions.apply_manual_gpx_result(
        session_id,
        start_time=start_time,
        end_time=end_time,
        duration_sec=duration_sec,
        sensors=sensors,
        has_analysis=has_analysis,
        status="ready",
        error=error,
    )
