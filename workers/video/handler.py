"""SailFrames video worker — MP4 → HLS via ffmpeg.

Consolidates the old MediaConvert-based trio (transcode_video / transcode_complete /
link_videos) into one portable worker. Same `lambda_handler(event, context)`
signature and the same S3 conventions, so it runs identically on AWS Lambda
(container image) and locally in Docker (Lambda RIE), and works against MinIO
(`SAILFRAMES_S3_ENDPOINT`) as well as AWS S3.

Trigger: S3 ObjectCreated on ``raw/{device_id}/{date}/video/{camera}/{file}.mp4``.
Output: an HLS rendition (1080p H.264, 6s segments) under
``hls/{device_id}/{date}/{camera}/``.
"""

import logging
import os
import re
import subprocess
import tempfile
from urllib.parse import unquote_plus
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DATA_BUCKET = os.environ.get("DATA_BUCKET") or os.environ.get(
    "SAILFRAMES_BUCKET", "sailframes-fleet-data-prod"
)
# 6s segments, 1080p, ~5 Mbps — matches the retired MediaConvert output.
SEGMENT_SECONDS = int(os.environ.get("HLS_SEGMENT_SECONDS", "6"))
LOCAL_TZ = ZoneInfo(os.environ.get("VIDEO_LOCAL_TZ", "America/New_York"))


def _s3():
    # Honor a MinIO/S3-compatible endpoint for local runs.
    endpoint = os.environ.get("SAILFRAMES_S3_ENDPOINT")
    return boto3.client("s3", endpoint_url=endpoint) if endpoint else boto3.client("s3")


def lambda_handler(event, context):
    """Transcode every newly uploaded MP4 in the event to HLS."""
    results = []
    for record in event.get("Records", []):
        try:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
        except (KeyError, TypeError):
            continue
        if not key.endswith(".mp4") or "/video/" not in key:
            logger.info("Skipping non-video key: %s", key)
            continue
        try:
            out_prefix = _transcode(bucket, key)
            results.append({"key": key, "hls": out_prefix})
        except Exception:  # pragma: no cover - defensive, keeps batch going
            logger.exception("Transcode failed for %s", key)
            results.append({"key": key, "error": True})
    return {"processed": len(results), "results": results}


def _transcode(bucket: str, key: str) -> str:
    # raw/{device_id}/{date}/video/{camera}/{filename}.mp4
    parts = key.split("/")
    if len(parts) < 6:
        raise ValueError(f"Unexpected video key structure: {key}")
    device_id, date, camera, filename = parts[1], parts[2], parts[4], parts[5]

    # UTC timestamp from the filename (e.g. cockpit_20260324_130339.mp4).
    m = re.search(r"(\d{8}_\d{6})", filename)
    if m:
        local_dt = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=LOCAL_TZ)
        utc_ts = local_dt.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
    else:
        utc_ts = "0"

    s3 = _s3()
    out_prefix = f"hls/{device_id}/{date}/{camera}/"

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "input.mp4")
        s3.download_file(bucket, key, src)

        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)
        playlist = os.path.join(out_dir, f"playlist_{utc_ts}.m3u8")
        seg_pattern = os.path.join(out_dir, f"segment_{utc_ts}_%03d.ts")

        cmd = [
            "ffmpeg", "-y", "-i", src,
            "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast",
            "-b:v", "5000k", "-maxrate", "5000k", "-bufsize", "10000k",
            # Align keyframes to segment boundaries so each .ts is independently seekable.
            "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
            "-c:a", "aac", "-b:a", "128k",
            "-f", "hls", "-hls_time", str(SEGMENT_SECONDS),
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", seg_pattern,
            playlist,
        ]
        logger.info("ffmpeg: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True)

        for name in sorted(os.listdir(out_dir)):
            s3.upload_file(
                os.path.join(out_dir, name),
                bucket,
                out_prefix + name,
                ExtraArgs={"ContentType": _content_type(name)},
            )

    logger.info("HLS written to s3://%s/%s", bucket, out_prefix)
    return out_prefix


def _content_type(name: str) -> str:
    if name.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if name.endswith(".ts"):
        return "video/mp2t"
    return "application/octet-stream"
