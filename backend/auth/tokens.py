"""JWT access tokens + opaque refresh tokens.

Access tokens are stateless JWTs (HS256, secret from ``SAILFRAMES_JWT_SECRET``)
validated without a DB hit. Refresh tokens are opaque random strings; only
their SHA-256 hash is ever persisted (see ``AuthTokenRepo``). Rotation identity
(``family_id``) and reuse detection are handled by the auth router.

Cookie names + a ``cookie_secure()`` helper live here so ``current_user`` and
the auth router agree on them.
"""

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

ACCESS_COOKIE = "sf_access"
REFRESH_COOKIE = "sf_refresh"
CSRF_COOKIE = "sf_csrf"

# Refresh cookie is scoped to the auth subtree so it reaches /refresh AND
# /logout (both need it) but nothing else.
REFRESH_COOKIE_PATH = "/api/auth"

_ACCESS_TTL_MIN = int(os.environ.get("SAILFRAMES_ACCESS_TTL_MIN", "15"))
_REFRESH_TTL_DAYS = int(os.environ.get("SAILFRAMES_REFRESH_TTL_DAYS", "30"))


def _secret() -> str:
    s = os.environ.get("SAILFRAMES_JWT_SECRET")
    if not s:
        raise RuntimeError("SAILFRAMES_JWT_SECRET must be set for native login")
    return s


def cookie_secure() -> bool:
    """Whether to set the ``Secure`` cookie flag. Default on; set
    ``SAILFRAMES_COOKIE_SECURE=0`` for local plain-HTTP testing."""
    return os.environ.get("SAILFRAMES_COOKIE_SECURE", "1").lower() not in ("0", "false", "")


# --- Access JWT ---

def issue_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_ACCESS_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_access_token(token: str) -> Optional[uuid.UUID]:
    """Return the user id from a valid, unexpired access token, else None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except Exception:
        return None


def access_max_age() -> int:
    return _ACCESS_TTL_MIN * 60


# --- Refresh (opaque) ---

def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_family_id() -> str:
    return uuid.uuid4().hex


def refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS)


def refresh_max_age() -> int:
    return _REFRESH_TTL_DAYS * 24 * 3600


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def is_expired(expires_at: Optional[datetime]) -> bool:
    """Rows are TIMESTAMPTZ, so psycopg hands back aware datetimes."""
    if expires_at is None:
        return False
    return datetime.now(timezone.utc) >= expires_at
