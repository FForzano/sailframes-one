"""SQL app_config repository: the singleton settings row (see
``db/models/app_config.py``). ``seed_app_config`` (``auth/seed.py``)
guarantees the row exists on startup, so ``get()`` normally never returns
``None`` — callers still handle it defensively (e.g. a fresh DB before the
first startup seed has run).
"""

from typing import Optional

from sqlalchemy import select

from ...db.models import AppConfigORM


class SqlAppConfigRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def get(self) -> Optional[AppConfigORM]:
        with self.Session() as s:
            return s.scalars(select(AppConfigORM)).first()

    def update(self, changes: dict) -> AppConfigORM:
        with self.Session() as s:
            orm = s.scalars(select(AppConfigORM)).first()
            for k, v in changes.items():
                setattr(orm, k, v)
            s.commit()
        return self.get()
