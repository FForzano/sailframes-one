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
    "generator_model": "claude-opus-4-7",
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
ANTHROPIC_SECRET_ARN = os.environ.get("ANTHROPIC_SECRET_ARN", "")
NOTIFY_TOPIC_ARN = os.environ.get(
    "NOTIFY_TOPIC_ARN",
    "arn:aws:sns:us-east-1:581790374840:sailframes-coach-notifications",
)

GENERATOR_MODEL = "claude-opus-4-7"

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


GENERATE_PROMPT = """\
You are producing a written coach debrief for ONE boat in ONE race. The output
will be reviewed by a human coach — they will edit, approve, or delete each
paragraph before it is sent back to the skipper. Length cap: 4-6 paragraphs,
~100-140 words each, total under 700 words.

Subject boat: {team_name} (device {device_id})
Race: {race_name}
Date: {race_date} (venue local time)

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

The race data (boats, GPS, IMU, wind, course, finishing positions, etc.):
```json
{race_data_json}
```

Call submit_briefing with your paragraphs.
"""


OVERVIEW_PROMPT = """\
You are producing a written RACE OVERVIEW debrief — a single report covering
the whole race across all boats, not one skipper. The output will be reviewed
by a human coach, edited and approved paragraph-by-paragraph, and delivered
to the whole fleet (or used by a coach as a teaching artifact). Length cap:
4-6 paragraphs, ~100-140 words each, total under 700 words.

Race: {race_name}
Date: {race_date} (venue local time)

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

The race data (boats, GPS, IMU, wind, course, finishing positions, etc.):
```json
{race_data_json}
```

Call submit_briefing with your paragraphs.
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


def _compact_for_opus(race, data, focal_device_id=None):
    """Down-sample sensor streams so the prompt stays under context limits.

    Per-boat briefing: focal boat at 1Hz GPS+IMU, others at 5s GPS only.
    Race overview (focal_device_id=None): every boat at 2s GPS, no IMU.
    """

    def downsample(samples, step_sec):
        if not samples:
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

    overview_mode = focal_device_id is None
    compact = {"race": race, "boats": {}}
    for dev, b in (data.get("boats") or {}).items():
        sensors = b.get("sensors") or {}
        focal = (not overview_mode) and (dev == focal_device_id)
        if overview_mode:
            gps_step, imu_step = 2, None
        elif focal:
            gps_step, imu_step = 1, 1
        else:
            gps_step, imu_step = 5, None
        compact["boats"][dev] = {
            "boat": b.get("boat", {}),
            "sensors": {
                "gps": downsample(sensors.get("gps") or [], gps_step),
                "imu": downsample(sensors.get("imu") or [], imu_step) if imu_step else [],
                "wind": sensors.get("wind") or [],
            },
        }
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
    post. Returns dict {email, is_coach, name}."""
    headers = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise PermissionError("missing bearer token")
    token = auth.split(None, 1)[1].strip()

    # Session tokens are gated on COACH_ALLOWLIST at issuance — but we
    # re-derive is_coach from the allowlist here so the flag tracks the
    # actual moderation source of truth even if session-token issuance
    # is ever widened.
    if token.startswith("sf."):
        email = _verify_session_token(token)
        return {"email": email, "is_coach": email in COACH_ALLOWLIST, "name": ""}

    # Google ID token — accept any verified email; flag is_coach
    # separately so the route handler can decide moderation rights.
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
        "is_coach": email in COACH_ALLOWLIST,
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
    if is_overview:
        team_name = "Race overview"
        # Compact every boat at moderate cadence — no focal subject.
        compact = _compact_for_opus(race, data, focal_device_id=None)
    else:
        boat = (data.get("boats") or {}).get(device_id, {}).get("boat", {}) or {}
        team_name = boat.get("team_name") or boat.get("boat_name") or device_id
        compact = _compact_for_opus(race, data, focal_device_id=device_id)
    race_name = race.get("name") or race_id
    race_date = race.get("date") or ""

    prompt_template = OVERVIEW_PROMPT if is_overview else GENERATE_PROMPT
    prompt = prompt_template.format(
        team_name=team_name,
        device_id=device_id,
        race_name=race_name,
        race_date=race_date,
        race_data_json=json.dumps(compact, ensure_ascii=False),
    )

    response = _anthropic().messages.create(
        model=GENERATOR_MODEL,
        max_tokens=8000,
        tools=[SUBMIT_BRIEFING_TOOL],
        tool_choice={"type": "tool", "name": "submit_briefing"},
        messages=[{"role": "user", "content": prompt}],
    )

    paragraphs_raw = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_briefing":
            paragraphs_raw = block.input.get("paragraphs", [])
            break
    if not paragraphs_raw:
        raise RuntimeError("Opus did not call submit_briefing")

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
        "generator_model": GENERATOR_MODEL,
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
            # `is_mine` / `is_mod` per post — but never leak the raw
            # author_email back to public callers (PII; would otherwise
            # end up in browser caches and any forwarded JSON).
            viewer_email = None
            viewer_is_coach = False
            try:
                ai = _verify_open_request(event)
                viewer_email = ai["email"]
                viewer_is_coach = ai["is_coach"]
            except Exception:
                pass
            safe_posts = []
            for p in posts:
                pe = (p.get("author_email") or "").lower()
                safe = {
                    "id": p.get("id"),
                    "author_name": p.get("author_name"),
                    "is_coach": bool(p.get("is_coach")),
                    "body": p.get("body"),
                    "cursor_t_sec": p.get("cursor_t_sec"),
                    "created_at": p.get("created_at"),
                }
                if viewer_email and pe == viewer_email:
                    safe["is_mine"] = True
                if viewer_is_coach:
                    safe["is_mod"] = True
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
        is_coach = auth_info["is_coach"]
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
            post = {
                "id": uuid.uuid4().hex,
                "author_email": email,
                "author_name": display_name,
                "is_coach": is_coach,
                "body": text,
                "cursor_t_sec": cursor_t_sec,
                "created_at": _now_iso(),
            }
            doc = _load_discussion(race_id)
            doc.setdefault("posts", []).append(post)
            doc["race_id"] = race_id
            _save_discussion(race_id, doc)

            # Notify the admin of every new post. Includes a deep link so
            # the recipient can jump straight to the discussion.
            author_label = display_name or email
            role = "coach" if is_coach else "guest"
            preview = (text[:300] + "…") if len(text) > 300 else text
            _notify_admin(
                subject=f"[SailFrames] Tactics post by {author_label}",
                body=(
                    f"New tactics-discussion post on race {race_id}\n"
                    f"\n"
                    f"Author : {author_label} ({email}) — {role}\n"
                    f"Posted : {post['created_at']}\n"
                    f"\n"
                    f"---\n"
                    f"{preview}\n"
                    f"---\n"
                    f"\n"
                    f"View: https://sailframes.com/race.html?race_id={race_id}\n"
                ),
            )
            return _resp(200, post)

        if method == "DELETE" and len(parts) == 4:
            post_id = parts[3]
            doc = _load_discussion(race_id)
            posts = doc.get("posts") or []
            target = next((p for p in posts if p.get("id") == post_id), None)
            if target is None:
                return _resp(404, {"error": "post not found"})
            owner_match = (target.get("author_email") or "").lower() == email
            if not is_coach and not owner_match:
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
