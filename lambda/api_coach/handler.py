"""SailFrames coach-review Lambda.

Endpoints (deployed as a Lambda Function URL, mode: BUFFERED, auth: NONE):
  OPTIONS *                                   → CORS preflight (no auth)
  POST   /generate                            → generate canonical briefing for (race, boat) via Opus
  GET    /briefings                           → list all stored briefings (dashboard)
  GET    /briefings/{race_id}/{device_id}     → fetch one briefing
  PUT    /briefings/{race_id}/{device_id}     → save edited/approved/deleted state (full doc)
  DELETE /briefings/{race_id}/{device_id}     → permanently delete a stored briefing from S3

Every non-OPTIONS request requires `Authorization: Bearer <google-id-token>`.
The token is verified against Google, and the email is checked against
COACH_ALLOWLIST (env var, comma-separated). Anything else → 401 / 403.

Storage layout (S3, bucket = LOG_BUCKET):
  coach-briefings/{race_id}/{device_id}.json    — full briefing doc

Briefing JSON schema:
  {
    "race_id": "...",
    "device_id": "...",
    "team_name": "...",
    "race_name": "...",
    "race_date": "YYYY-MM-DD",
    "generated_at": "ISO-8601",
    "generator_model": "claude-sonnet-4-6" (per-boat) | "claude-opus-4-7" (overview),
    "status": "draft" | "in_review" | "approved" | "exported",
    "reviewer_email": "...",
    "reviewer_started_at": "ISO-8601",
    "last_modified_at": "ISO-8601",
    "paragraphs": [
      {
        "id": "p1",
        "section": "Start",
        "text_original": "...",
        "text_edited": null | "...",
        "status": "pending" | "approved" | "deleted",
        "reviewed_at": null | "ISO-8601",
        "reviewed_by": null | "email",
        "image": null | { "type": "race_map_segment" | "tack_analysis" | "speed_chart_segment",
                          "t_start_iso": "...", "t_end_iso": "...", "rationale": "..." }
      },
      ...
    ]
  }
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
import uuid
from datetime import datetime, timezone

import boto3
from anthropic import Anthropic
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token


_s3 = boto3.client("s3")
_secrets = boto3.client("secretsmanager")
_sns = boto3.client("sns")
# 240 s read timeout: a single screenshot can take ~70-90 s on cold start
# (Chromium init + page nav + tile load + render). Default boto3 read_timeout
# is 60 s — that was killing every auto-capture after the first one.
from botocore.config import Config as _BotoConfig
_lambda_client = boto3.client(
    "lambda",
    config=_BotoConfig(read_timeout=240, connect_timeout=10, retries={"max_attempts": 1}),
)
SCREENSHOT_FUNCTION_NAME = os.environ.get("SCREENSHOT_FUNCTION_NAME", "sailframes-api-screenshot")
_anthropic_cached = None
_anthropic_key_cached = None

LOG_BUCKET = os.environ.get("LOG_BUCKET", "sailframes-fleet-data-prod")
RACE_API_BASE = os.environ.get(
    "RACE_API_BASE",
    "https://rnngzx7flk.execute-api.us-east-1.amazonaws.com",
)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
COACH_ALLOWLIST = {
    e.strip().lower()
    for e in os.environ.get("COACH_ALLOWLIST", "").split(",")
    if e.strip()
}
# Distinct from COACH_ALLOWLIST (which gates long-lived session token
# issuance for the coach-review app). ADMIN_ALLOWLIST gates only
# moderation power on the public discussion board — currently just
# the platform owner. Authors can always delete their own posts.
ADMIN_ALLOWLIST = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_ALLOWLIST", "avillach@gmail.com").split(",")
    if e.strip()
}
ANTHROPIC_SECRET_ARN = os.environ.get("ANTHROPIC_SECRET_ARN", "")
NOTIFY_TOPIC_ARN = os.environ.get(
    "NOTIFY_TOPIC_ARN",
    "arn:aws:sns:us-east-1:581790374840:sailframes-coach-notifications",
)

# Model split (mirrors the chat box: Sonnet for routine work, Opus only
# for the big synthesis report).
#   • Per-boat briefings are routine, high-volume "here's how your crew
#     did" reports — Sonnet handles them well at ~1/5 the per-token cost
#     of Opus.
#   • The whole-fleet RACE OVERVIEW is the one synthesis report where
#     Opus's extra reasoning earns its price — same logic as the chat
#     box's "Full debrief" chip.
# Override per-deploy via env if the tradeoff ever shifts.
OVERVIEW_MODEL = os.environ.get("OVERVIEW_MODEL", "claude-opus-4-7")
BOAT_MODEL = os.environ.get("BOAT_MODEL", "claude-sonnet-4-6")
# Back-compat alias (referenced in the schema docstring / older stored docs).
GENERATOR_MODEL = OVERVIEW_MODEL


def _model_for(is_overview):
    return OVERVIEW_MODEL if is_overview else BOAT_MODEL

# --- Long-lived session tokens ------------------------------------------
# Google ID tokens expire after 1 hour, which is too aggressive for a
# coach session where the same person reviews briefings across days.
# After a successful Google sign-in the client calls
# POST /session/exchange and gets back a 30-day HS256 JWT-shape token
# (prefixed "sf." so _verify_request can tell it apart from a real
# Google ID token at zero cost).
_SESSION_LIFETIME_SEC = 30 * 24 * 3600   # 30 days
_SESSION_VERSION = "v1"

def _session_signing_key():
    explicit = os.environ.get("SESSION_TOKEN_SECRET", "").strip()
    if explicit:
        return hashlib.sha256(explicit.encode("utf-8")).digest()
    # Derived stable key — cold-start safe, depends only on values
    # that don't change across deploys. Set SESSION_TOKEN_SECRET to a
    # 32+ byte random string to rotate.
    seed = (
        f"sailframes-coach-session::{_SESSION_VERSION}::"
        f"{GOOGLE_CLIENT_ID}::{LOG_BUCKET}"
    )
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _b64u_encode(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64u_decode(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _make_session_token(email):
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "v": _SESSION_VERSION,
        "sub": email,
        "iat": now,
        "exp": now + _SESSION_LIFETIME_SEC,
    }
    payload_b64 = _b64u_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_session_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"sf.{payload_b64}.{_b64u_encode(sig)}"


def _verify_session_token(token):
    """Return the email on success; raise PermissionError otherwise."""
    if not token or not token.startswith("sf."):
        raise PermissionError("not a session token")
    parts = token.split(".")
    if len(parts) != 3:
        raise PermissionError("malformed session token")
    _, payload_b64, sig_b64 = parts
    expected = hmac.new(_session_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    try:
        given = _b64u_decode(sig_b64)
    except Exception:
        raise PermissionError("session signature decode failed")
    if not hmac.compare_digest(expected, given):
        raise PermissionError("session signature mismatch")
    try:
        payload = json.loads(_b64u_decode(payload_b64))
    except Exception:
        raise PermissionError("session payload decode failed")
    if payload.get("v") != _SESSION_VERSION:
        raise PermissionError("session version mismatch")
    exp = payload.get("exp", 0)
    now = int(datetime.now(timezone.utc).timestamp())
    if not isinstance(exp, (int, float)) or now > exp:
        raise PermissionError(f"session expired ({exp} < {now})")
    email = (payload.get("sub") or "").lower()
    if not email:
        raise PermissionError("session has no subject")
    if COACH_ALLOWLIST and email not in COACH_ALLOWLIST:
        raise PermissionError(f"{email} not in coach allowlist")
    return email



# -------------------- Anthropic --------------------


def _anthropic_key():
    """Fetch the Anthropic API key from Secrets Manager (same secret as
    api_chat). Cached after first call. Falls back to env var for local
    testing."""
    global _anthropic_key_cached
    if _anthropic_key_cached is not None:
        return _anthropic_key_cached
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        _anthropic_key_cached = env_key
        return env_key
    if not ANTHROPIC_SECRET_ARN:
        raise RuntimeError("Neither ANTHROPIC_API_KEY nor ANTHROPIC_SECRET_ARN configured")
    raw = _secrets.get_secret_value(SecretId=ANTHROPIC_SECRET_ARN)
    s = raw.get("SecretString", "")
    # Secret may be a plain string or JSON like {"ANTHROPIC_API_KEY": "sk-..."}
    try:
        parsed = json.loads(s)
        s = parsed.get("ANTHROPIC_API_KEY") or parsed.get("api_key") or s
    except Exception:
        pass
    _anthropic_key_cached = s
    return s


def _anthropic():
    global _anthropic_cached
    if _anthropic_cached is None:
        _anthropic_cached = Anthropic(api_key=_anthropic_key())
    return _anthropic_cached


SUBMIT_BRIEFING_TOOL = {
    "name": "submit_briefing",
    "description": (
        "Submit a structured race debrief of 4-6 paragraphs for human coach review. "
        "Each paragraph stands on its own, so a coach can approve, edit, or delete "
        "any one without breaking the others."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "paragraphs": {
                "type": "array",
                "minItems": 4,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "description": (
                                "Short topic header (≤30 chars), e.g. 'Start', "
                                "'First beat', 'Mark 1 rounding', 'Tactics', "
                                "'Boat handling'."
                            ),
                        },
                        "text": {
                            "type": "string",
                            "description": (
                                "Coach-quality paragraph, 100-140 words. Direct, "
                                "second-person ('your start', 'you tacked'). "
                                "Cite venue local times. Reference opponent boats "
                                "by team name. When citing a Racing Rule of "
                                "Sailing, name it (e.g., 'RRS 10 — On opposite "
                                "tacks'). No filler, no headings inside the text."
                            ),
                        },
                        "image_hint": {
                            "type": "object",
                            "description": (
                                "Optional: which auxiliary image best illustrates "
                                "this paragraph. Use type='none' if no image "
                                "would help."
                            ),
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "race_map_segment",
                                        "tack_analysis",
                                        "speed_chart_segment",
                                        "none",
                                    ],
                                },
                                "t_start_iso": {"type": "string"},
                                "t_end_iso": {"type": "string"},
                                "rationale": {
                                    "type": "string",
                                    "description": "One sentence on what the image will show.",
                                },
                            },
                            "required": ["type"],
                        },
                    },
                    "required": ["section", "text"],
                },
            }
        },
        "required": ["paragraphs"],
    },
}


# The prompts are split into a STABLE system block (style guide / task
# framing — identical across every per-boat briefing, so it sits at the
# front of the cacheable prefix) and a VOLATILE user block (boat identity
# + race data). cache_control goes on the big user block, so regenerating
# the same boat within the 5-min TTL reads the whole prefix from cache
# instead of re-billing it. See `_generate_briefing`.
GENERATE_SYSTEM = """\
You are producing a written coach debrief for ONE boat in ONE race. The output
will be reviewed by a human coach — they will edit, approve, or delete each
paragraph before it is sent back to the skipper. Length cap: 4-6 paragraphs,
~100-140 words each, total under 700 words.

Style:
  • Direct, concrete, second-person ('your start', 'you tacked at 14:32:08').
  • Always cite venue-local times in HH:MM:SS, never UTC.
  • Reference specific opponent boats by team name.
  • When citing a Racing Rule of Sailing, name the rule (e.g., "RRS 10 — On
    opposite tacks", "RRS 18 — Mark-room").
  • No introductory fluff, no headings inside paragraphs, no "Dear sailor".
  • Each paragraph must stand on its own — a coach must be able to delete one
    without breaking the surrounding ones.

For each paragraph, propose an `image_hint` only if a specific visual would
materially help the skipper see what you're describing. Use type='none'
otherwise.

Call submit_briefing with your paragraphs.
"""

GENERATE_USER = """\
Subject boat: {team_name} (device {device_id})
Race: {race_name}
Date: {race_date} (venue local time)

The race data (boats, GPS, IMU, wind, course, finishing positions, etc.):
```json
{race_data_json}
```
"""


OVERVIEW_SYSTEM = """\
You are producing a written RACE OVERVIEW debrief — a single report covering
the whole race across all boats, not one skipper. The output will be reviewed
by a human coach, edited and approved paragraph-by-paragraph, and delivered
to the whole fleet (or used by a coach as a teaching artifact). Length cap:
4-6 paragraphs, ~100-140 words each, total under 700 words.

Style:
  • Third-person, addressing the fleet collectively. Name the boats by team
    when you call them out (e.g., 'Mystic Mutiny got the favored end at the
    pin, while Anchor Management lined up mid-line and was buried at the gun').
  • Always cite venue-local times in HH:MM:SS, never UTC.
  • When citing a Racing Rule of Sailing, name the rule.
  • No 'Dear racers'. Each paragraph stands alone.
  • Cover: conditions and wind picture; the start (who got it, who didn't);
    decisive tactical moments on the course; mark roundings or decisive
    passing lanes; finish order with a one-line lesson per top finisher.
  • Be opinionated about WHY positions changed — strategy, boat handling,
    boat speed, luck — not just descriptions of what happened.

For each paragraph, propose an `image_hint` only if a specific visual would
help (typically `race_map_segment` framing the relevant time window of the
race). Use type='none' otherwise.

Call submit_briefing with your paragraphs.
"""

OVERVIEW_USER = """\
Race: {race_name}
Date: {race_date} (venue local time)

The race data (boats, GPS, IMU, wind, course, finishing positions, etc.):
```json
{race_data_json}
```
"""

# Sentinel "device_id" for the race-wide overview report. Anything starting
# with an underscore is reserved (real device IDs are E1..E6).
RACE_OVERVIEW_ID = "_race"


def _fetch_race(race_id):
    """Pull race definition + sensor data from the existing race API."""
    race_url = f"{RACE_API_BASE}/api/races/{race_id}"
    data_url = f"{RACE_API_BASE}/api/races/{race_id}/data?sensors=gps,imu,wind"
    with urllib.request.urlopen(race_url, timeout=15) as r:
        race = json.loads(r.read())
    with urllib.request.urlopen(data_url, timeout=30) as r:
        data = json.loads(r.read())
    return race, data


# Long-context premium pricing kicks in above 200K input tokens on both
# Sonnet 4.6 and Opus 4.7 (≈2× the input price). Keep the serialized
# race-data block comfortably under that so a briefing never trips the
# premium tier — regardless of race length. We estimate tokens from the
# JSON char count (dense numeric JSON runs ~3.5 chars/token; dividing by
# 3.5 over-counts tokens a touch, which only makes us coarsen sooner —
# the safe direction) and progressively halve the cadence until it fits.
DATA_TOKEN_BUDGET = 140_000          # headroom under 200K for system + tool schema + output
_CHARS_PER_TOKEN = 3.5


def _downsample(samples, step_sec):
    if not samples or not step_sec:
        return []
    out = []
    last_t = -1e18
    for s in samples:
        t = s.get("t")
        if not t:
            continue
        tms = _iso_to_ms(t)
        if tms is None:
            continue
        if tms - last_t >= step_sec * 1000:
            out.append(s)
            last_t = tms
    return out


def _build_compact(race, data, focal_device_id, gps_focal_step, imu_focal_step, gps_other_step):
    """One down-sample pass. The focal boat gets the fine cadence
    (gps_focal_step + IMU); every other boat gets gps_other_step, no IMU.
    Overview mode (focal_device_id=None): all boats at gps_other_step."""
    overview_mode = focal_device_id is None
    compact = {"race": race, "boats": {}}
    for dev, b in (data.get("boats") or {}).items():
        sensors = b.get("sensors") or {}
        focal = (not overview_mode) and (dev == focal_device_id)
        if focal:
            gps_step, imu_step = gps_focal_step, imu_focal_step
        else:
            gps_step, imu_step = gps_other_step, None
        compact["boats"][dev] = {
            "boat": b.get("boat", {}),
            "sensors": {
                "gps": _downsample(sensors.get("gps") or [], gps_step),
                "imu": _downsample(sensors.get("imu") or [], imu_step) if imu_step else [],
                "wind": sensors.get("wind") or [],
            },
        }
    return compact


def _compact_for_briefing(race, data, focal_device_id=None):
    """Down-sample sensor streams for the prompt, then coarsen the cadence
    if the serialized block exceeds DATA_TOKEN_BUDGET (keeping the request
    under the 200K long-context premium threshold).

    Base cadence — per-boat briefing: focal boat 1Hz GPS + 1Hz IMU, others
    5s GPS only. Race overview (focal_device_id=None): every boat 2s GPS,
    no IMU. Long races coarsen in 2× steps until they fit.
    """
    overview_mode = focal_device_id is None
    if overview_mode:
        gps_focal, imu_focal, gps_other = 2, None, 2
    else:
        gps_focal, imu_focal, gps_other = 1, 1, 5

    char_budget = int(DATA_TOKEN_BUDGET * _CHARS_PER_TOKEN)
    coarsen = 1
    compact = None
    for _ in range(7):                       # up to 64× coarsening
        compact = _build_compact(
            race, data, focal_device_id,
            gps_focal * coarsen,
            (imu_focal * coarsen) if imu_focal else None,
            gps_other * coarsen,
        )
        size = len(json.dumps(compact, ensure_ascii=False))
        if size <= char_budget:
            if coarsen > 1:
                print(f"[compact] coarsened {coarsen}x to ~{size // 1000}KB "
                      f"(focal={focal_device_id})")
            return compact
        coarsen *= 2

    print(f"[compact] WARNING: ~{len(json.dumps(compact)) // 1000}KB after "
          f"{coarsen // 2}x coarsening (focal={focal_device_id})")
    return compact


def _iso_to_ms(s):
    try:
        s2 = s.replace("Z", "+00:00") if s.endswith("Z") else s
        return int(datetime.fromisoformat(s2).timestamp() * 1000)
    except Exception:
        return None


# -------------------- Auth --------------------


def _verify_request(event):
    """Returns the authenticated email or raises an exception."""
    headers = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise PermissionError("missing bearer token")
    token = auth.split(None, 1)[1].strip()

    # Long-lived session tokens are prefixed "sf." — verify locally with
    # HMAC, no network round-trip to Google. The vast majority of
    # authenticated requests after sign-in take this fast path.
    if token.startswith("sf."):
        return _verify_session_token(token)

    # Fall back to verifying a Google ID token (1-hour lifetime). This
    # is only hit by /session/exchange right after sign-in, since the
    # client immediately swaps the Google ID token for our session
    # token and uses the latter for every subsequent call.
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID not configured")
    info = id_token.verify_oauth2_token(
        token, g_requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=30
    )
    email = (info.get("email") or "").lower()
    if not info.get("email_verified"):
        raise PermissionError("email not verified")
    if COACH_ALLOWLIST and email not in COACH_ALLOWLIST:
        raise PermissionError(f"{email} not in coach allowlist")
    return email


# -------------------- Storage --------------------


def _briefing_key(race_id, device_id):
    safe_race = race_id.replace("/", "_")
    safe_dev = device_id.replace("/", "_")
    return f"coach-briefings/{safe_race}/{safe_dev}.json"


def _load_briefing(race_id, device_id):
    try:
        obj = _s3.get_object(Bucket=LOG_BUCKET, Key=_briefing_key(race_id, device_id))
        return json.loads(obj["Body"].read())
    except _s3.exceptions.NoSuchKey:
        return None


def _save_briefing(briefing):
    briefing["last_modified_at"] = _now_iso()
    _s3.put_object(
        Bucket=LOG_BUCKET,
        Key=_briefing_key(briefing["race_id"], briefing["device_id"]),
        Body=json.dumps(briefing, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def _list_briefings():
    out = []
    paginator = _s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=LOG_BUCKET, Prefix="coach-briefings/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            # key = coach-briefings/{race_id}/{device_id}.json
            parts = key.split("/")
            if len(parts) != 3:
                continue
            try:
                body = _s3.get_object(Bucket=LOG_BUCKET, Key=key)
                doc = json.loads(body["Body"].read())
                approved = sum(
                    1 for p in doc.get("paragraphs", []) if p.get("status") == "approved"
                )
                total = len(doc.get("paragraphs", []))
                out.append(
                    {
                        "race_id": doc.get("race_id", parts[1]),
                        "device_id": doc.get("device_id", parts[2].rsplit(".", 1)[0]),
                        "team_name": doc.get("team_name"),
                        "race_name": doc.get("race_name"),
                        "race_date": doc.get("race_date"),
                        "status": doc.get("status", "draft"),
                        "generated_at": doc.get("generated_at"),
                        "last_modified_at": doc.get("last_modified_at"),
                        "approved_count": approved,
                        "total_count": total,
                    }
                )
            except Exception as e:  # noqa: BLE001
                print(f"[list_briefings] skip {key}: {e}")
                continue
    out.sort(key=lambda x: (x.get("race_date") or "", x.get("race_id") or ""), reverse=True)
    return out


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -------------------- Discussions (per-race tactics board) --------------------
#
# Public read, open-auth write. Anyone with a verified Google email may
# post; coaches (members of COACH_ALLOWLIST) get moderation power
# (delete any post). Authors can delete their own.
#
# Auth model: coaches authenticate with their existing 30-day session
# token (sf.*). Guests send a fresh Google ID token per request (1-hour
# Google lifetime), which is fine for occasional posters. We don't issue
# session tokens to non-coach users — that would widen the trust surface
# of every other coach endpoint.
#
# Storage: one JSON doc per race at coach-discussions/{race_id}.json
# with posts ordered by created_at ascending. List-append concurrency
# is best-effort — at single-digit posts/minute the race window is
# negligible.

_DISCUSSION_PREFIX = "coach-discussions/"
_DISCUSSION_BODY_MAX = 4000   # chars per post
_DISCUSSION_PAGE_MAX = 500    # max posts per race returned in one GET


def _discussion_key(race_id):
    return f"{_DISCUSSION_PREFIX}{race_id.replace('/', '_')}.json"


def _load_discussion(race_id):
    try:
        obj = _s3.get_object(Bucket=LOG_BUCKET, Key=_discussion_key(race_id))
        return json.loads(obj["Body"].read())
    except _s3.exceptions.NoSuchKey:
        return {"race_id": race_id, "posts": []}


def _save_discussion(race_id, doc):
    _s3.put_object(
        Bucket=LOG_BUCKET,
        Key=_discussion_key(race_id),
        Body=json.dumps(doc, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def _notify_admin(subject, body):
    """Fire-and-forget SNS publish for admin notifications. Never raises
    — a notification failure must NEVER fail the user-facing request."""
    if not NOTIFY_TOPIC_ARN:
        return
    try:
        _sns.publish(
            TopicArn=NOTIFY_TOPIC_ARN,
            Subject=subject[:99],   # SNS hard limit is 100 chars
            Message=body,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[notify] sns publish failed: {e}")


def _verify_open_request(event):
    """Like _verify_request but does NOT enforce the coach allowlist —
    used only by the discussion endpoints so verified competitors can
    post. Returns dict {email, is_admin, name}. The "coach vs sailor"
    label is a user-chosen post role, NOT derived here from any
    allowlist; this helper only resolves identity + admin power."""
    headers = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise PermissionError("missing bearer token")
    token = auth.split(None, 1)[1].strip()

    if token.startswith("sf."):
        email = _verify_session_token(token)
        return {"email": email, "is_admin": email in ADMIN_ALLOWLIST, "name": ""}

    # Google ID token — accept any verified email; admin flag is
    # checked against the smaller ADMIN_ALLOWLIST.
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID not configured")
    info = id_token.verify_oauth2_token(
        token, g_requests.Request(), GOOGLE_CLIENT_ID, clock_skew_in_seconds=30
    )
    if not info.get("email_verified"):
        raise PermissionError("email not verified")
    email = (info.get("email") or "").lower()
    if not email:
        raise PermissionError("token has no email")
    return {
        "email": email,
        "is_admin": email in ADMIN_ALLOWLIST,
        "name": (info.get("name") or "").strip(),
    }


def _shorten_email(email):
    """Fallback display name: local-part of the email, capitalized."""
    if not email or "@" not in email:
        return email or ""
    local = email.split("@", 1)[0]
    return local.replace(".", " ").replace("_", " ").title()


# -------------------- Generation --------------------


def _generate_briefing(race_id, device_id):
    race, data = _fetch_race(race_id)
    is_overview = device_id == RACE_OVERVIEW_ID
    model = _model_for(is_overview)
    if is_overview:
        team_name = "Race overview"
        # Compact every boat at moderate cadence — no focal subject.
        compact = _compact_for_briefing(race, data, focal_device_id=None)
        system_text = OVERVIEW_SYSTEM
        user_template = OVERVIEW_USER
    else:
        boat = (data.get("boats") or {}).get(device_id, {}).get("boat", {}) or {}
        team_name = boat.get("team_name") or boat.get("boat_name") or device_id
        compact = _compact_for_briefing(race, data, focal_device_id=device_id)
        system_text = GENERATE_SYSTEM
        user_template = GENERATE_USER
    race_name = race.get("name") or race_id
    race_date = race.get("date") or ""

    user_text = user_template.format(
        team_name=team_name,
        device_id=device_id,
        race_name=race_name,
        race_date=race_date,
        race_data_json=json.dumps(compact, ensure_ascii=False),
    )

    # Prompt caching: the stable style guide goes in `system`; the big
    # per-boat race-data block is the cache breakpoint. Regenerating the
    # same target within the 5-min TTL reads the whole prefix from cache
    # (~0.1× input price) instead of re-billing it.
    response = _anthropic().messages.create(
        model=model,
        max_tokens=8000,
        system=[{"type": "text", "text": system_text}],
        tools=[SUBMIT_BRIEFING_TOOL],
        tool_choice={"type": "tool", "name": "submit_briefing"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    )

    # Cache visibility in CloudWatch — confirms reads actually land
    # (Opus was at 0% cache reads before this change).
    u = getattr(response, "usage", None)
    if u is not None:
        print(
            f"[generate] model={model} device={device_id} "
            f"in={getattr(u, 'input_tokens', '?')} "
            f"cache_write={getattr(u, 'cache_creation_input_tokens', 0)} "
            f"cache_read={getattr(u, 'cache_read_input_tokens', 0)} "
            f"out={getattr(u, 'output_tokens', '?')}"
        )

    paragraphs_raw = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_briefing":
            paragraphs_raw = block.input.get("paragraphs", [])
            break
    if not paragraphs_raw:
        raise RuntimeError(f"{model} did not call submit_briefing")

    paragraphs = []
    for i, p in enumerate(paragraphs_raw, start=1):
        img_hint = p.get("image_hint")
        if img_hint and img_hint.get("type") == "none":
            img_hint = None
        paragraphs.append(
            {
                "id": f"p{i}",
                "section": p.get("section", f"Section {i}"),
                "text_original": p.get("text", ""),
                "text_edited": None,
                "status": "pending",
                "reviewed_at": None,
                "reviewed_by": None,
                "image": img_hint,
            }
        )

    return {
        "race_id": race_id,
        "device_id": device_id,
        "team_name": team_name,
        "race_name": race_name,
        "race_date": race_date,
        "generated_at": _now_iso(),
        "generator_model": model,
        "status": "draft",
        "reviewer_email": None,
        "reviewer_started_at": None,
        "last_modified_at": _now_iso(),
        "paragraphs": paragraphs,
    }


# -------------------- HTTP --------------------


# NOTE: CORS headers are configured on the Lambda Function URL itself
# (AllowOrigins/AllowMethods/AllowHeaders/MaxAge in the URL config). We
# must NOT add CORS headers from the handler too — duplicate headers
# (e.g. two Access-Control-Allow-Origin) cause the browser to reject the
# response with a generic "Load failed" / network error.


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, _ctx):
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "GET").upper()
    path = event.get("rawPath") or "/"

    if method == "OPTIONS":
        # Function URL handles preflight headers; just return 204.
        return {"statusCode": 204, "body": ""}

    # ----- Public (no-auth) endpoints, evaluated BEFORE the auth gate -----
    # /discussions/* — per-race tactics board. GET is fully public.
    # POST/DELETE use a wider auth gate (_verify_open_request) that
    # accepts any verified Google email, not just the coach allowlist —
    # so competitors can post questions/observations without being
    # added to COACH_ALLOWLIST by hand.
    if path.startswith("/discussions/"):
        parts = path.split("/")
        # Expect /discussions/{race_id} (3 parts) or /discussions/{race_id}/{post_id} (4).
        if len(parts) < 3 or not parts[2]:
            return _resp(404, {"error": "no_route", "method": method, "path": path})
        race_id = parts[2]

        if method == "GET" and len(parts) == 3:
            doc = _load_discussion(race_id)
            posts = doc.get("posts") or []
            if len(posts) > _DISCUSSION_PAGE_MAX:
                posts = posts[-_DISCUSSION_PAGE_MAX:]
            # Opportunistically authenticate the viewer so we can stamp
            # `is_mine` / `is_admin_mod` / `my_vote` per post — but
            # never leak the raw author_email back to public callers.
            viewer_email = None
            viewer_is_admin = False
            try:
                ai = _verify_open_request(event)
                viewer_email = ai["email"]
                viewer_is_admin = ai["is_admin"]
            except Exception:
                pass
            safe_posts = []
            for p in posts:
                pe = (p.get("author_email") or "").lower()
                # Role: explicit `role` field wins. Legacy posts (no
                # role field) default to "sailor" so the old auto-coach
                # badge no longer surfaces.
                role = (p.get("role") or "").lower()
                if role not in ("coach", "sailor"):
                    role = "sailor"
                votes = p.get("votes") or {}
                up_list   = votes.get("up") or []
                down_list = votes.get("down") or []
                safe = {
                    "id": p.get("id"),
                    "author_name": p.get("author_name"),
                    "role": role,
                    "body": p.get("body"),
                    "cursor_t_sec": p.get("cursor_t_sec"),
                    "created_at": p.get("created_at"),
                    "upvotes": len(up_list),
                    "downvotes": len(down_list),
                }
                if viewer_email:
                    if pe == viewer_email:
                        safe["is_mine"] = True
                    up_lower   = {e.lower() for e in up_list}
                    down_lower = {e.lower() for e in down_list}
                    if viewer_email in up_lower:
                        safe["my_vote"] = "up"
                    elif viewer_email in down_lower:
                        safe["my_vote"] = "down"
                if viewer_is_admin:
                    safe["is_admin_mod"] = True
                safe_posts.append(safe)
            return _resp(200, {"race_id": race_id, "posts": safe_posts})

        # Mutating ops need auth (but NOT the strict coach allowlist).
        try:
            auth_info = _verify_open_request(event)
        except (PermissionError, ValueError) as e:
            return _resp(401, {"error": "unauthorized", "detail": str(e)})
        except Exception as e:  # noqa: BLE001
            return _resp(500, {"error": "auth_error", "detail": str(e)})
        email = auth_info["email"]
        is_admin = auth_info["is_admin"]
        display_name = auth_info["name"] or _shorten_email(email)

        if method == "POST" and len(parts) == 3:
            body = json.loads(event.get("body") or "{}")
            text = (body.get("body") or "").strip()
            if not text:
                return _resp(400, {"error": "body required"})
            if len(text) > _DISCUSSION_BODY_MAX:
                return _resp(400, {
                    "error": f"body too long (max {_DISCUSSION_BODY_MAX} chars)",
                })
            cursor_t_sec = body.get("cursor_t_sec")
            if cursor_t_sec is not None:
                try:
                    cursor_t_sec = float(cursor_t_sec)
                except (TypeError, ValueError):
                    cursor_t_sec = None
            role = (body.get("role") or "sailor").lower()
            if role not in ("coach", "sailor"):
                role = "sailor"
            post = {
                "id": uuid.uuid4().hex,
                "author_email": email,
                "author_name": display_name,
                "role": role,
                "body": text,
                "cursor_t_sec": cursor_t_sec,
                "created_at": _now_iso(),
                "votes": {"up": [], "down": []},
            }
            doc = _load_discussion(race_id)
            doc.setdefault("posts", []).append(post)
            doc["race_id"] = race_id
            _save_discussion(race_id, doc)

            # Notify the admin of every new post. The client passes a
            # rich race-context label ("Regatta · Race N of M · Tue May 12,
            # 2026") so the email names the race in fleet terms instead
            # of an opaque race_id. Falls back to race_id for any old
            # client that doesn't send the field.
            author_label = display_name or email
            race_label = (body.get("race_context_label") or "").strip() or race_id
            preview = (text[:300] + "…") if len(text) > 300 else text
            _notify_admin(
                subject=f"[SailFrames] Tactics — {race_label} — post by {author_label}",
                body=(
                    f"New tactics-discussion post.\n"
                    f"\n"
                    f"Race   : {race_label}\n"
                    f"Race ID: {race_id}\n"
                    f"Author : {author_label} ({email}) — self-tagged as {role}\n"
                    f"Posted : {post['created_at']}\n"
                    f"\n"
                    f"---\n"
                    f"{preview}\n"
                    f"---\n"
                    f"\n"
                    f"View: https://sailframes.com/race.html?race={race_id}&tactics=1\n"
                ),
            )
            # Return the post WITHOUT author_email (consistent w/ GET).
            return _resp(200, {
                "id": post["id"],
                "author_name": post["author_name"],
                "role": post["role"],
                "body": post["body"],
                "cursor_t_sec": post["cursor_t_sec"],
                "created_at": post["created_at"],
                "upvotes": 0,
                "downvotes": 0,
                "is_mine": True,
            })

        # POST /discussions/{race_id}/{post_id}/vote — toggle/cast a vote.
        # Authors can't vote on their own posts (enforced both sides).
        # NOTE: read-modify-write on the per-race doc has a small race
        # window if two users vote simultaneously; acceptable at fleet
        # scale. Upgrade to S3 conditional writes if traffic grows.
        if method == "POST" and len(parts) == 5 and parts[4] == "vote":
            post_id = parts[3]
            req = json.loads(event.get("body") or "{}")
            vote = (req.get("vote") or "").lower().strip()
            if vote not in ("up", "down", "none"):
                return _resp(400, {"error": "vote must be 'up', 'down', or 'none'"})
            doc = _load_discussion(race_id)
            posts = doc.get("posts") or []
            target = next((p for p in posts if p.get("id") == post_id), None)
            if target is None:
                return _resp(404, {"error": "post not found"})
            if (target.get("author_email") or "").lower() == email:
                return _resp(400, {"error": "cannot vote on your own post"})
            votes = target.setdefault("votes", {"up": [], "down": []})
            votes.setdefault("up", [])
            votes.setdefault("down", [])
            # Clear any existing vote from this user, then apply.
            votes["up"]   = [e for e in votes["up"]   if e.lower() != email]
            votes["down"] = [e for e in votes["down"] if e.lower() != email]
            if vote == "up":   votes["up"].append(email)
            if vote == "down": votes["down"].append(email)
            _save_discussion(race_id, doc)
            return _resp(200, {
                "id": post_id,
                "upvotes": len(votes["up"]),
                "downvotes": len(votes["down"]),
                "my_vote": vote if vote != "none" else None,
            })

        if method == "DELETE" and len(parts) == 4:
            post_id = parts[3]
            doc = _load_discussion(race_id)
            posts = doc.get("posts") or []
            target = next((p for p in posts if p.get("id") == post_id), None)
            if target is None:
                return _resp(404, {"error": "post not found"})
            owner_match = (target.get("author_email") or "").lower() == email
            if not is_admin and not owner_match:
                return _resp(403, {"error": "not authorized"})
            doc["posts"] = [p for p in posts if p.get("id") != post_id]
            _save_discussion(race_id, doc)
            return _resp(200, {"deleted": True, "id": post_id})

        return _resp(404, {"error": "no_route", "method": method, "path": path})

    # GET /race-wind-default/{race_id} — race.html reads this on every load
    # to honor the admin's wind-station override. Public because race.html
    # has no user auth.
    if method == "GET" and path.startswith("/race-wind-default/"):
        parts = path.split("/")
        if len(parts) == 3:
            race_id = parts[2]
            key = f"coach-overrides/wind-station/{race_id.replace('/', '_')}.json"
            try:
                obj = _s3.get_object(Bucket=LOG_BUCKET, Key=key)
                return _resp(200, json.loads(obj["Body"].read()))
            except _s3.exceptions.NoSuchKey:
                return _resp(404, {"error": "no_default_set"})
            except Exception as e:  # noqa: BLE001
                return _resp(500, {"error": "read_failed", "detail": str(e)})

    try:
        email = _verify_request(event)
    except (PermissionError, ValueError) as e:
        # Invalid/expired/malformed token — frontend treats 401 as
        # "session ended" and bounces back to the login page.
        return _resp(401, {"error": "unauthorized", "detail": str(e)})
    except Exception as e:  # noqa: BLE001
        return _resp(500, {"error": "auth_error", "detail": str(e)})

    try:
        # POST /session/exchange — caller authenticates with a Google
        # ID token (just-after-sign-in), we return our own 30-day
        # session JWT for subsequent requests so the coach session
        # doesn't expire every hour.
        if method == "POST" and path == "/session/exchange":
            return _resp(200, {
                "session_token": _make_session_token(email),
                "email": email,
                "expires_in": _SESSION_LIFETIME_SEC,
            })

        if method == "POST" and path == "/generate":
            body = json.loads(event.get("body") or "{}")
            race_id = body.get("race_id")
            device_id = body.get("device_id")
            if not race_id or not device_id:
                return _resp(400, {"error": "race_id and device_id required"})
            briefing = _generate_briefing(race_id, device_id)
            briefing["reviewer_email"] = email
            briefing["reviewer_started_at"] = _now_iso()
            briefing["status"] = "in_review"
            _save_briefing(briefing)
            return _resp(200, briefing)

        if method == "GET" and path == "/briefings":
            return _resp(200, {"briefings": _list_briefings()})

        if method == "GET" and path.startswith("/briefings/"):
            parts = path.split("/")
            if len(parts) == 4:
                race_id, device_id = parts[2], parts[3]
                briefing = _load_briefing(race_id, device_id)
                if briefing is None:
                    return _resp(404, {"error": "not_found"})
                return _resp(200, briefing)

        # PUT /race-wind-default/{race_id} — admin override of the wind
        # station for this race. Body: {"station_id": "..."}. Persisted in
        # S3; the race page reads via the public GET above on every load.
        if method == "PUT" and path.startswith("/race-wind-default/"):
            parts = path.split("/")
            if len(parts) == 3:
                race_id = parts[2]
                req = json.loads(event.get("body") or "{}")
                station_id = (req.get("station_id") or "").strip()
                if not station_id:
                    return _resp(400, {"error": "station_id required"})
                doc = {
                    "race_id": race_id,
                    "station_id": station_id,
                    "set_by": email,
                    "set_at": _now_iso(),
                }
                key = f"coach-overrides/wind-station/{race_id.replace('/', '_')}.json"
                _s3.put_object(
                    Bucket=LOG_BUCKET, Key=key,
                    Body=json.dumps(doc).encode("utf-8"),
                    ContentType="application/json",
                )
                return _resp(200, doc)

        # DELETE /race-wind-default/{race_id} — clear the override so the
        # race falls back to the priority-based auto-pick.
        if method == "DELETE" and path.startswith("/race-wind-default/"):
            parts = path.split("/")
            if len(parts) == 3:
                race_id = parts[2]
                key = f"coach-overrides/wind-station/{race_id.replace('/', '_')}.json"
                try:
                    _s3.delete_object(Bucket=LOG_BUCKET, Key=key)
                except Exception as e:  # noqa: BLE001
                    return _resp(500, {"error": "delete_failed", "detail": str(e)})
                return _resp(200, {"cleared": True})

        if method == "POST" and path == "/capture":
            # Proxy to the Puppeteer screenshot Lambda. Frontend keeps
            # talking only to this coach Lambda (auth + allowlist already
            # enforced above); the screenshot Lambda is private.
            req = json.loads(event.get("body") or "{}")
            if not req.get("race_id"):
                return _resp(400, {"error": "race_id required"})
            try:
                inv = _lambda_client.invoke(
                    FunctionName=SCREENSHOT_FUNCTION_NAME,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(req).encode("utf-8"),
                )
                raw = inv["Payload"].read()
                if inv.get("FunctionError"):
                    return _resp(502, {"error": "screenshot_lambda_error", "detail": raw.decode("utf-8", "ignore")[:1000]})
                # The screenshot Lambda returns a Lambda-response shape
                # (statusCode + headers + body string). Unwrap to the
                # actual JSON payload so the coach app sees a flat result.
                inner = json.loads(raw)
                inner_status = int(inner.get("statusCode", 200))
                inner_body_str = inner.get("body") or "{}"
                try:
                    inner_body = json.loads(inner_body_str)
                except Exception:
                    inner_body = {"raw": inner_body_str}
                return _resp(inner_status, inner_body)
            except Exception as e:  # noqa: BLE001
                return _resp(500, {"error": "capture_invoke_failed", "detail": str(e)})

        if method == "DELETE" and path.startswith("/briefings/"):
            parts = path.split("/")
            if len(parts) == 4:
                race_id, device_id = parts[2], parts[3]
                key = _briefing_key(race_id, device_id)
                try:
                    _s3.delete_object(Bucket=LOG_BUCKET, Key=key)
                except Exception as e:  # noqa: BLE001
                    return _resp(500, {"error": "delete_failed", "detail": str(e)})
                return _resp(200, {"deleted": True, "race_id": race_id, "device_id": device_id})

        if method == "PUT" and path.startswith("/briefings/"):
            parts = path.split("/")
            if len(parts) == 4:
                race_id, device_id = parts[2], parts[3]
                body = json.loads(event.get("body") or "{}")
                existing = _load_briefing(race_id, device_id) or {}
                # Only update mutable fields. Identity fields are taken from the
                # path so a malicious client can't rewrite a different briefing.
                merged = {
                    **existing,
                    "race_id": race_id,
                    "device_id": device_id,
                    "team_name": body.get("team_name") or existing.get("team_name"),
                    "race_name": body.get("race_name") or existing.get("race_name"),
                    "race_date": body.get("race_date") or existing.get("race_date"),
                    "paragraphs": body.get("paragraphs", existing.get("paragraphs", [])),
                    "attachments": body.get("attachments", existing.get("attachments", [])),
                    "status": body.get("status") or existing.get("status", "in_review"),
                    "reviewer_email": email,
                }
                # Stamp reviewer_at on changed paragraphs.
                for p in merged["paragraphs"]:
                    if p.get("_dirty"):
                        p["reviewed_at"] = _now_iso()
                        p["reviewed_by"] = email
                        p.pop("_dirty", None)
                _save_briefing(merged)
                return _resp(200, merged)

        return _resp(404, {"error": "no_route", "method": method, "path": path})
    except Exception as e:  # noqa: BLE001
        print(f"[handler] error: {e}")
        return _resp(500, {"error": "server_error", "detail": str(e)})
