"""Self-hosted (MinIO) ingest webhook (``POST /hooks/minio``).

Receives MinIO bucket-notification events and dispatches them to the standalone
processing workers — the self-hosted replacement for the AWS S3 ObjectCreated →
Lambda trigger. CSV uploads go to the ``process_upload`` worker; MP4 uploads go
to the ``video`` worker. Both are separate containers exposing the AWS Lambda
Runtime Interface (``POST /2015-03-31/functions/function/invocations``), so the
*same* images run on Lambda in the cloud.

After the ``process_upload`` worker returns, the freshly processed sessions are
attributed to their boat here (that needs the DB/repos, which the worker doesn't
carry). The worker URLs are configured via env; unset means that upload class is
ignored (e.g. video disabled).
"""

import logging
import os
import urllib.parse

import requests
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["ingest"])

logger = logging.getLogger(__name__)

HOOK_TOKEN = os.environ.get("SAILFRAMES_HOOK_TOKEN")
PROCESS_UPLOAD_URL = os.environ.get("PROCESS_UPLOAD_URL")
VIDEO_WORKER_URL = os.environ.get("VIDEO_WORKER_URL")
WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT_SEC", "300"))


def _invoke_worker(url: str, records: list) -> object:
    """POST an S3-shaped event to a worker's Lambda RIE endpoint."""
    resp = requests.post(url, json={"Records": records}, timeout=WORKER_TIMEOUT)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return resp.text


def _attribute_sessions(records: list) -> None:
    """Resolve each freshly processed session's device→boat snapshot and persist
    ``boat_id``/``boat`` (Phase 4/5). Best-effort and idempotent: never overwrites
    a session already claimed (``owner_user_id`` set), and uses
    ``DeviceRepo.resolve_boat`` (covering assignment window at ``start_time`` →
    ``default_boat_id`` → unclaimed)."""
    from ..repositories import get_repos

    repos = get_repos()
    seen = set()
    for record in records:
        try:
            key = record["s3"]["object"]["key"]  # raw/{device_id}/{date}/{file}.csv
        except (KeyError, TypeError):
            continue
        parts = key.split("/")
        if len(parts) < 4:
            continue
        device_id, date = parts[1], parts[2]
        if (device_id, date) in seen:
            continue
        seen.add((device_id, date))

        session = repos.sessions.get(device_id, date)
        if session is None or session.owner_user_id is not None:
            continue  # not processed yet, or already user-claimed — leave it
        at = session.start_time or date
        boat_id = repos.devices.resolve_boat(device_id, at)
        if boat_id and session.boat_id != boat_id:
            repos.sessions.attribute_boat(device_id, date, boat_id)


@router.post("/hooks/minio")
async def minio_hook(request: Request):
    """Receive a MinIO bucket-notification and route new uploads to the workers.

    MinIO posts an S3-compatible event body (``Records[].s3.object.key``), the
    same shape the workers expect. We gate on a shared token, URL-decode keys,
    split CSV vs MP4, dispatch each class to its worker, then attribute the
    freshly processed sessions to their boat."""
    if HOOK_TOKEN:
        auth = request.headers.get("authorization", "")
        presented = auth[7:] if auth.lower().startswith("bearer ") else auth
        if presented != HOOK_TOKEN:
            raise HTTPException(401, "Invalid hook token")

    event = await request.json()

    csv_records: list = []
    video_records: list = []
    for record in event.get("Records", []):
        try:
            raw_key = record["s3"]["object"]["key"]
        except (KeyError, TypeError):
            continue
        key = urllib.parse.unquote_plus(raw_key)
        record = {**record, "s3": {**record["s3"],
                                   "object": {**record["s3"]["object"], "key": key}}}
        # Only newly uploaded raw/ CSVs (skip markers / _health / _sd_health that
        # processing itself writes back into raw/) and raw/ video MP4s.
        if key.startswith("raw/") and key.endswith(".csv"):
            csv_records.append(record)
        elif key.endswith(".mp4") and "/video/" in key:
            video_records.append(record)

    result: dict = {"status": "ok", "processed": 0}

    if csv_records:
        if not PROCESS_UPLOAD_URL:
            raise HTTPException(503, "PROCESS_UPLOAD_URL not configured")
        result["process_upload"] = _invoke_worker(PROCESS_UPLOAD_URL, csv_records)
        result["processed"] += len(csv_records)
        # Attribute after processing; never let it fail the ingest.
        try:
            _attribute_sessions(csv_records)
        except Exception:  # pragma: no cover - defensive
            logger.exception("session boat-attribution failed (ingest still ok)")

    if video_records and VIDEO_WORKER_URL:
        result["video"] = _invoke_worker(VIDEO_WORKER_URL, video_records)
        result["processed"] += len(video_records)

    if not result["processed"]:
        return {"status": "ignored", "processed": 0}
    return result
