"""Repository factory.

``get_repos()`` returns a process-wide ``Repositories`` facade backed by
Postgres (SQLAlchemy). Large binary data is never DB-backed, so the repos also
hold the blob store for the few manifest-backfill paths that need it.
"""

import os

from ..storage import get_blob_store
from .base import Repositories
from .sql import build_sql_repos

_repos: Repositories | None = None


def build_repos() -> Repositories:
    data_prefix = os.environ.get("SAILFRAMES_DATA_PREFIX", "processed")
    return build_sql_repos(get_blob_store(), data_prefix)


def get_repos() -> Repositories:
    global _repos
    if _repos is None:
        _repos = build_repos()
    return _repos


__all__ = ["Repositories", "get_repos", "build_repos"]
