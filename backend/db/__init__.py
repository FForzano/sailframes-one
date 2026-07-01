"""Database engine + session factory for the Postgres metadata backend.

Lazily builds a SQLAlchemy engine and exposes a session factory plus
``init_db()`` (``create_all`` — fits the "new deployments only" scope; Alembic
can be layered on later).

The connection URL is built from discrete ``POSTGRES_*`` env vars via
``sqlalchemy.engine.URL.create()`` rather than string-concatenating a
``postgresql://user:pass@host/db`` URL by hand: that avoids ever holding the
password in a single plaintext connection-string env var (e.g. visible
verbatim in ``docker inspect`` / process listings as one token) and sidesteps
URL-escaping bugs if the password contains ``@``, ``:`` or ``/``. An explicit
``DATABASE_URL`` is still honored if set, for non-compose deployments.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from .base import Base
from . import models  # noqa: F401  (registers all tables on Base.metadata)

_engine = None
_SessionLocal = None


def _build_url():
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    database = os.environ.get("POSTGRES_DB")
    if not (user and password and database):
        raise RuntimeError(
            "SAILFRAMES_METADATA_BACKEND=postgres requires DATABASE_URL, or "
            "POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB (+ optional "
            "POSTGRES_HOST/POSTGRES_PORT)"
        )
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=database,
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_build_url(), pool_pre_ping=True, future=True)
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _SessionLocal


def run_migrations() -> None:
    """Run Alembic ``upgrade head`` programmatically, using the packaged
    ``alembic.ini`` (with an absolute ``script_location`` so CWD doesn't
    matter). env.py builds the URL from the same env vars as the app."""
    import pathlib

    from alembic import command
    from alembic.config import Config

    api_dir = pathlib.Path(__file__).resolve().parent.parent  # backend
    cfg = Config(str(api_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_dir / "alembic"))
    command.upgrade(cfg, "head")


def init_db() -> None:
    """Provision the schema. Alembic-managed when ``SAILFRAMES_USE_ALEMBIC`` is
    set (recommended once a DB carries data); otherwise ``create_all`` — fine
    for fresh deployments and unchanged from prior behaviour."""
    if os.environ.get("SAILFRAMES_USE_ALEMBIC"):
        run_migrations()
    else:
        Base.metadata.create_all(get_engine())


__all__ = ["Base", "get_engine", "get_sessionmaker", "init_db", "run_migrations"]
