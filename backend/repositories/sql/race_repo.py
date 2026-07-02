"""SQL race repository (aggregate: races + child marks/boats/result).

``save_dict`` upserts a full race dict (create or replace, rebuilding children);
routers build that dict from the request models (create) or from ``get().to_dict()``
+ changes (update). Reads return ``RaceORM``; ``list_summaries`` returns light dicts.
"""

from typing import Optional

from sqlalchemy import select

from ...db.models import RaceORM, MarkORM, RaceBoatORM, RaceResultORM


class SqlRaceRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list_summaries(self, *, regatta_id=None, date=None, raceday_id=None) -> list[dict]:
        with self.Session() as s:
            stmt = select(RaceORM)
            if regatta_id:
                stmt = stmt.where(RaceORM.regatta_id == regatta_id)
            if date:
                stmt = stmt.where(RaceORM.date == date)
            if raceday_id:
                stmt = stmt.where(RaceORM.raceday_id == raceday_id)
            return [_summary(r) for r in s.scalars(stmt).all()]

    def get(self, race_id: str) -> Optional[RaceORM]:
        with self.Session() as s:
            return s.get(RaceORM, race_id)

    def save_dict(self, data: dict) -> RaceORM:
        rid = data["race_id"]
        with self.Session() as s:
            orm = s.get(RaceORM, rid)
            if orm is None:
                orm = RaceORM(race_id=rid)
                s.add(orm)
            orm.name = data.get("name")
            orm.date = data.get("date")
            orm.start_time = data.get("start_time")
            orm.end_time = data.get("end_time")
            orm.regatta_id = data.get("regatta_id")
            orm.raceday_id = data.get("raceday_id")
            orm.start_line = data.get("start_line")
            orm.finish_line = data.get("finish_line")
            orm.course = list(data.get("course") or [])
            orm.finish_order = list(data.get("finish_order") or [])
            orm.created_at = data.get("created_at")
            orm.updated_at = data.get("updated_at")
            orm.marks = [
                MarkORM(mark_id=m.get("mark_id"), name=m.get("name") or "",
                        mark_type=m.get("mark_type") or "custom", lat=m.get("lat"), lon=m.get("lon"))
                for m in (data.get("marks") or [])
            ]
            orm.boats = [
                RaceBoatORM(device_id=b.get("device_id"), boat_id=b.get("boat_id"),
                            boat_name=b.get("boat_name") or "", sail_number=b.get("sail_number") or "",
                            session_path=b.get("session_path"), gpx_path=b.get("gpx_path"), polar=b.get("polar"))
                for b in (data.get("boats") or [])
            ]
            results = data.get("results")
            if results is not None:
                orm.result = RaceResultORM(
                    finish_order=list(results.get("finish_order") or []),
                    boat_results=dict(results.get("boat_results") or {}),
                    computed_at=results.get("computed_at"),
                )
            else:
                orm.result = None
            s.commit()
        return self.get(rid)

    def delete(self, race_id: str) -> bool:
        with self.Session() as s:
            orm = s.get(RaceORM, race_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True


def _summary(orm: RaceORM) -> dict:
    return {
        "race_id": orm.race_id,
        "name": orm.name,
        "date": orm.date,
        "start_time": orm.start_time,
        "end_time": orm.end_time,
        "regatta_id": orm.regatta_id,
        "raceday_id": orm.raceday_id,
        "boat_count": len(orm.boats),
    }
