"""SQL race-day repository. Reads return ``RaceDayORM``; writes take dicts."""

from typing import Optional

from sqlalchemy import select

from ...db.models import RaceDayORM


class SqlRaceDayRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[RaceDayORM]:
        with self.Session() as s:
            return list(s.scalars(select(RaceDayORM)).all())

    def get(self, raceday_id: str) -> Optional[RaceDayORM]:
        with self.Session() as s:
            return s.get(RaceDayORM, raceday_id)

    def create(self, data: dict) -> RaceDayORM:
        with self.Session() as s:
            orm = RaceDayORM(raceday_id=data["raceday_id"])
            orm.date = data.get("date")
            orm.type = data.get("type") or "race_day"
            orm.name = data.get("name")
            orm.regatta_id = data.get("regatta_id")
            orm.race_ids = list(data.get("race_ids") or [])
            orm.created_at = data.get("created_at")
            orm.updated_at = data.get("updated_at")
            s.add(orm)
            s.commit()
        return self.get(data["raceday_id"])

    def update(self, raceday_id: str, changes: dict) -> Optional[RaceDayORM]:
        with self.Session() as s:
            orm = s.get(RaceDayORM, raceday_id)
            if orm is None:
                return None
            for k, v in changes.items():
                setattr(orm, k, v)
            s.commit()
        return self.get(raceday_id)

    def delete(self, raceday_id: str) -> bool:
        with self.Session() as s:
            orm = s.get(RaceDayORM, raceday_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True
