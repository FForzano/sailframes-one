"""SQL boat catalog repository (+ standing crew membership). Reads return
``BoatORM``; ``create``/``update`` take dicts (membership is managed via the
dedicated member methods so a boat edit never clobbers the roster)."""

from typing import Optional

from sqlalchemy import select, update

from ...db.models import BoatORM, BoatMemberORM

_SCALARS = ("name", "type", "sail_number", "club", "notes")


class SqlBoatRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[BoatORM]:
        with self.Session() as s:
            return list(s.scalars(select(BoatORM)).all())

    def get(self, boat_id: str) -> Optional[BoatORM]:
        with self.Session() as s:
            return s.get(BoatORM, boat_id)

    def create(self, data: dict) -> BoatORM:
        with self.Session() as s:
            orm = BoatORM(boat_id=data["boat_id"])
            for k in _SCALARS:
                setattr(orm, k, data.get(k) or "")
            orm.club_id = data.get("club_id")
            orm.loa_m = data.get("loa_m")
            orm.skippers = list(data.get("skippers") or [])
            orm.photos = dict(data.get("photos") or {})
            orm.cert_url = data.get("cert_url")
            orm.mbsa_url = data.get("mbsa_url")
            orm.links = list(data.get("links") or [])
            orm.polar = data.get("polar")
            orm.created_at = data.get("created_at")
            orm.updated_at = data.get("updated_at")
            s.add(orm)
            s.commit()
        return self.get(data["boat_id"])

    def update(self, boat_id: str, changes: dict) -> Optional[BoatORM]:
        with self.Session() as s:
            orm = s.get(BoatORM, boat_id)
            if orm is None:
                return None
            # Membership is never rewritten here (dedicated member methods do that).
            for k, v in changes.items():
                if k == "members":
                    continue
                setattr(orm, k, v)
            s.commit()
        return self.get(boat_id)

    def delete(self, boat_id: str) -> bool:
        with self.Session() as s:
            orm = s.get(BoatORM, boat_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True

    # --- standing crew ---

    def add_member(self, boat_id: str, *, user_id: int, role: str = "crew",
                   created_at: Optional[str] = None) -> bool:
        with self.Session() as s:
            if s.get(BoatORM, boat_id) is None:
                return False
            exists = s.scalars(
                select(BoatMemberORM).where(
                    BoatMemberORM.boat_id == boat_id, BoatMemberORM.user_id == user_id
                )
            ).first()
            if exists is not None:
                return False
            s.add(BoatMemberORM(boat_id=boat_id, user_id=user_id, role=role, created_at=created_at))
            s.commit()
            return True

    def remove_member(self, boat_id: str, user_id: int) -> bool:
        with self.Session() as s:
            orm = s.scalars(
                select(BoatMemberORM).where(
                    BoatMemberORM.boat_id == boat_id, BoatMemberORM.user_id == user_id
                )
            ).first()
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True

    def set_member_role(self, boat_id: str, user_id: int, role: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(BoatMemberORM)
                .where(BoatMemberORM.boat_id == boat_id, BoatMemberORM.user_id == user_id)
                .values(role=role)
            )
            s.commit()
            return res.rowcount > 0

    def list_members(self, boat_id: str) -> "list[BoatMemberORM]":
        with self.Session() as s:
            return list(s.scalars(
                select(BoatMemberORM).where(BoatMemberORM.boat_id == boat_id)
            ).all())

    def is_member(self, boat_id: str, user_id: int, roles: "Optional[list]" = None) -> bool:
        with self.Session() as s:
            q = select(BoatMemberORM).where(
                BoatMemberORM.boat_id == boat_id, BoatMemberORM.user_id == user_id
            )
            if roles is not None:
                q = q.where(BoatMemberORM.role.in_(roles))
            return s.scalars(q).first() is not None
