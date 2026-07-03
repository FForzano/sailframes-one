"""SQL boat repository (+ ownership membership via ``user_boats``). Reads
return ``BoatORM``; ``create``/``update`` take dicts (membership is managed via
the dedicated member methods so a boat edit never clobbers the roster)."""

import uuid
from typing import Optional

from sqlalchemy import select, update

from ...db.models import BoatORM, UserBoatORM

_FIELDS = ("name", "type", "sail_number", "loa_m", "cert_id", "mbsa_id", "notes", "club_id")


class SqlBoatRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[BoatORM]:
        with self.Session() as s:
            return list(s.scalars(select(BoatORM)).all())

    def get(self, boat_id: uuid.UUID) -> Optional[BoatORM]:
        with self.Session() as s:
            return s.get(BoatORM, boat_id)

    def create(self, data: dict) -> BoatORM:
        with self.Session() as s:
            orm = BoatORM(**{k: data.get(k) for k in _FIELDS})
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get(new_id)

    def update(self, boat_id: uuid.UUID, changes: dict) -> Optional[BoatORM]:
        with self.Session() as s:
            orm = s.get(BoatORM, boat_id)
            if orm is None:
                return None
            # Membership is never rewritten here (dedicated member methods do that).
            for k, v in changes.items():
                if k in _FIELDS:
                    setattr(orm, k, v)
            s.commit()
        return self.get(boat_id)

    def delete(self, boat_id: uuid.UUID) -> bool:
        with self.Session() as s:
            orm = s.get(BoatORM, boat_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True

    # --- ownership membership (user_boats) ---

    def add_member(self, boat_id: uuid.UUID, *, user_id: uuid.UUID,
                   role: str = "visitor",
                   default_sailing_role: Optional[str] = None) -> bool:
        with self.Session() as s:
            if s.get(BoatORM, boat_id) is None:
                return False
            exists = s.scalars(
                select(UserBoatORM).where(
                    UserBoatORM.boat_id == boat_id, UserBoatORM.user_id == user_id
                )
            ).first()
            if exists is not None:
                return False
            s.add(UserBoatORM(boat_id=boat_id, user_id=user_id, role=role,
                              default_sailing_role=default_sailing_role))
            s.commit()
            return True

    def remove_member(self, boat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        with self.Session() as s:
            orm = s.scalars(
                select(UserBoatORM).where(
                    UserBoatORM.boat_id == boat_id, UserBoatORM.user_id == user_id
                )
            ).first()
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True

    def set_member_role(self, boat_id: uuid.UUID, user_id: uuid.UUID, role: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(UserBoatORM)
                .where(UserBoatORM.boat_id == boat_id, UserBoatORM.user_id == user_id)
                .values(role=role)
            )
            s.commit()
            return res.rowcount > 0

    def list_members(self, boat_id: uuid.UUID) -> "list[UserBoatORM]":
        with self.Session() as s:
            return list(s.scalars(
                select(UserBoatORM).where(UserBoatORM.boat_id == boat_id)
            ).all())

    def is_member(self, boat_id: uuid.UUID, user_id: uuid.UUID,
                  roles: "Optional[list]" = None) -> bool:
        with self.Session() as s:
            q = select(UserBoatORM).where(
                UserBoatORM.boat_id == boat_id, UserBoatORM.user_id == user_id
            )
            if roles is not None:
                q = q.where(UserBoatORM.role.in_(roles))
            return s.scalars(q).first() is not None
