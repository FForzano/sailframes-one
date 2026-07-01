"""Authentication & authorization for the SailFrames API.

- ``require_admin`` / ``require_permission`` — endpoint guards (permissions.py)
- Cloudflare cookie gate (cloudflare.py) — the non-Postgres path
- RBAC seed (seed.py) and password hashing (passwords.py)

``require_admin`` is kept as the broad gate existing endpoints already call;
``require_permission`` adds fine-grained, optionally club-scoped checks.
"""

from .permissions import (
    require_admin,
    require_permission,
    current_user,
    require_user,
    verify_csrf,
)
from .passwords import hash_password, verify_password
from .seed import seed_defaults, seed_superadmin

__all__ = [
    "require_admin",
    "require_permission",
    "current_user",
    "require_user",
    "verify_csrf",
    "hash_password",
    "verify_password",
    "seed_defaults",
    "seed_superadmin",
]
