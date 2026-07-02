"""Alembic environment for the SailFrames Postgres metadata backend.

Reuses the app's ``Base.metadata`` (so ``--autogenerate`` sees every table) and
the app's ``_build_url()`` (so migrations use the exact same connection config
as the running service). Puts the repo root on ``sys.path`` so
``import backend...`` works regardless of the CWD Alembic is invoked from.
"""

import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Repo root on path for ``import backend...``.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from backend.db.base import Base  # noqa: E402
import backend.db.models  # noqa: E402,F401  (registers all tables on Base.metadata)
from backend.db import _build_url  # noqa: E402

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = Base.metadata


def _url() -> str:
    # _build_url() returns a plain str (DATABASE_URL) or a SQLAlchemy URL built
    # from the POSTGRES_* vars. str(URL) MASKS the password as "***", so render
    # it explicitly with the password intact for the migration connection.
    u = _build_url()
    return u if isinstance(u, str) else u.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
