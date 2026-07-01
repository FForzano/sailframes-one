"""SQL boat catalog repository (+ standing crew membership)."""

from typing import Optional

from sqlalchemy import select, update

from ... import domain
from ...db.models import BoatORM, BoatMemberORM
from ..base import BoatRepo
from . import _mappers as M


class SqlBoatRepo(BoatRepo):
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[domain.Boat]:
        with self.Session() as s:
            return [M.boat_to_domain(b) for b in s.scalars(select(BoatORM)).all()]

    def get(self, boat_id: str) -> Optional[domain.Boat]:
        with self.Session() as s:
            orm = s.get(BoatORM, boat_id)
            return M.boat_to_domain(orm) if orm else None

    def save(self, boat: domain.Boat) -> domain.Boat:
        with self.Session() as s:
            orm = s.get(BoatORM, boat.boat_id)
            if orm is None:
                orm = BoatORM(boat_id=boat.boat_id)
                s.add(orm)
            M.apply_boat(orm, boat)
            s.commit()
        return boat

    def delete(self, boat_id: str) -> bool:
        with self.Session() as s:
            orm = s.get(BoatORM, boat_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True

    # --- standing crew ---

    def add_member(self, boat_id: str, member: domain.BoatMember) -> bool:
        with self.Session() as s:
            if s.get(BoatORM, boat_id) is None:
                return False
            exists = s.scalars(
                select(BoatMemberORM).where(
                    BoatMemberORM.boat_id == boat_id,
                    BoatMemberORM.user_id == member.user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(BoatMemberORM(
                boat_id=boat_id,
                user_id=member.user_id,
                role=member.role,
                created_at=member.created_at,
            ))
            s.commit()
            return True

    def remove_member(self, boat_id: str, user_id: int) -> bool:
        with self.Session() as s:
            orm = s.scalars(
                select(BoatMemberORM).where(
                    BoatMemberORM.boat_id == boat_id,
                    BoatMemberORM.user_id == user_id,
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
                .where(
                    BoatMemberORM.boat_id == boat_id,
                    BoatMemberORM.user_id == user_id,
                )
                .values(role=role)
            )
            s.commit()
            return res.rowcount > 0

    def list_members(self, boat_id: str) -> "list[domain.BoatMember]":
        with self.Session() as s:
            rows = s.scalars(
                select(BoatMemberORM).where(BoatMemberORM.boat_id == boat_id)
            ).all()
            return [
                domain.BoatMember(user_id=m.user_id, role=m.role, created_at=m.created_at)
                for m in rows
            ]

    def is_member(self, boat_id: str, user_id: int, roles: "Optional[list[str]]" = None) -> bool:
        with self.Session() as s:
            q = select(BoatMemberORM).where(
                BoatMemberORM.boat_id == boat_id,
                BoatMemberORM.user_id == user_id,
            )
            if roles is not None:
                q = q.where(BoatMemberORM.role.in_(roles))
            return s.scalars(q).first() is not None
