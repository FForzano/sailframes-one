"""SQL (Postgres) repository backend.

``build_sql_repos`` initialises the schema (Alembic ``upgrade head``) and wires
the per-entity SQL repositories.

er-project phase: only the auth/RBAC set is wired (users, auth_tokens, clubs,
groups, boats). The session/device/race repos were deleted with the old schema
and get rewritten in the api-project phase; the facade exposes them as ``None``
until then. ``blob``/``data_prefix`` are accepted (and currently unused) so the
factory signature survives that rewrite.
"""

from ...db import get_sessionmaker, init_db
from ...storage import BlobStore
from ..base import Repositories
from .boat_repo import SqlBoatRepo
from .user_repo import SqlUserRepo
from .auth_token_repo import SqlAuthTokenRepo
from .club_repo import SqlClubRepo
from .group_repo import SqlGroupRepo


def build_sql_repos(blob: BlobStore, data_prefix: str) -> Repositories:
    init_db()
    sf = get_sessionmaker()
    return Repositories(
        users=SqlUserRepo(sf),
        auth_tokens=SqlAuthTokenRepo(sf),
        clubs=SqlClubRepo(sf),
        groups=SqlGroupRepo(sf),
        boats=SqlBoatRepo(sf),
    )


__all__ = [
    "build_sql_repos",
    "SqlBoatRepo",
    "SqlUserRepo",
    "SqlAuthTokenRepo",
    "SqlClubRepo",
    "SqlGroupRepo",
]
