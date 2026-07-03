"""Object upload proxy (streams a raw PUT body into the blob store).

Target for ``BlobStore.upload_ref`` on the MinIO/local backend, mirroring the
``/api/download/{key}`` proxy in ``download.py`` — MinIO's internal endpoint
host isn't reachable from the browser, so the "presigned URL" is this backend
route instead.

Unlike the download proxy, this one **must** be permissioned: it's a write, so
a bare key would let anyone overwrite arbitrary objects. Only manual-session
GPX uploads use this today, so the check is scoped to that one shape of key
(``raw/manual/{session_id}/...``) and the caller must be allowed to edit that
session.
"""

from fastapi import APIRouter, HTTPException, Request

from ._common import blob
from ..auth import require_user, verify_csrf

router = APIRouter(tags=["uploads"])


@router.put("/api/uploads/{key:path}")
async def upload_object(key: str, request: Request):
    from .sessions import _can_edit_session  # local import: avoid a router import cycle
    from ._common import repos

    verify_csrf(request)
    user = require_user(request)

    parts = key.split("/")
    if len(parts) < 3 or parts[0] != "raw" or parts[1] != "manual":
        raise HTTPException(403, "Upload not allowed for this key")
    try:
        session_id = int(parts[2])
    except ValueError:
        raise HTTPException(403, "Upload not allowed for this key")

    session = repos.sessions.get_by_id(session_id)
    if session is None or session.source != "manual":
        raise HTTPException(404, "Session not found")
    if not _can_edit_session(session, None, user):
        raise HTTPException(403, "Not allowed to upload to this session")

    body = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    blob.put_bytes(key, body, content_type)
    return {"status": "ok", "key": key}
