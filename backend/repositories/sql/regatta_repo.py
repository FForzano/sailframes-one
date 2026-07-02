"""SQL regatta repository. Reads return ``RegattaORM`` rows (``.to_dict()`` for
the wire); ``create``/``update`` take plain dicts of fields."""

from typing import Optional

from sqlalchemy import select

from ...db.models import RegattaORM


class SqlRegattaRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[RegattaORM]:
        with self.Session() as s:
            return list(s.scalars(select(RegattaORM)).all())

    def get(self, regatta_id: str) -> Optional[RegattaORM]:
        with self.Session() as s:
            return s.get(RegattaORM, regatta_id)

    def create(self, data: dict) -> RegattaORM:
        with self.Session() as s:
            orm = RegattaORM(regatta_id=data["regatta_id"])
            _apply(orm, data)
            s.add(orm)
            s.commit()
        return self.get(data["regatta_id"])

    def update(self, regatta_id: str, changes: dict) -> Optional[RegattaORM]:
        with self.Session() as s:
            orm = s.get(RegattaORM, regatta_id)
            if orm is None:
                return None
            for k, v in changes.items():
                setattr(orm, k, v)
            s.commit()
        return self.get(regatta_id)

    def delete(self, regatta_id: str) -> bool:
        with self.Session() as s:
            orm = s.get(RegattaORM, regatta_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True


def _apply(orm: RegattaORM, data: dict) -> None:
    orm.name = data.get("name")
    orm.venue = data.get("venue") or ""
    orm.boat_class = data.get("boat_class")
    orm.start_date = data.get("start_date")
    orm.end_date = data.get("end_date")
    orm.rating_system = data.get("rating_system")
    orm.start_sequence_minutes = data.get("start_sequence_minutes")
    orm.race_ids = list(data.get("race_ids") or [])
    orm.created_at = data.get("created_at")
    orm.updated_at = data.get("updated_at")
