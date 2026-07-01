"""SQL club repository (+ membership)."""

from typing import Optional

from sqlalchemy import select, update

from ... import domain
from ...db.models import ClubORM, ClubMemberORM
from ..base import ClubRepo
from . import _mappers as M


class SqlClubRepo(ClubRepo):
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[domain.Club]:
        with self.Session() as s:
            return [M.club_to_domain(c) for c in s.scalars(select(ClubORM)).all()]

    def get(self, club_id: int) -> Optional[domain.Club]:
        with self.Session() as s:
            orm = s.get(ClubORM, club_id)
            return M.club_to_domain(orm) if orm else None

    def save(self, club: domain.Club) -> domain.Club:
        with self.Session() as s:
            orm = s.get(ClubORM, club.id) if club.id is not None else None
            if orm is None:
                orm = ClubORM(name=club.name)
                s.add(orm)
            orm.name = club.name
            orm.owner_user_id = club.owner_user_id
            orm.default_session_visibility = club.default_session_visibility
            orm.created_at = club.created_at
            s.commit()
            club.id = orm.id
            return club

    def add_member(self, club_id: int, member: domain.ClubMember) -> bool:
        with self.Session() as s:
            exists = s.scalars(
                select(ClubMemberORM).where(
                    ClubMemberORM.club_id == club_id,
                    ClubMemberORM.user_id == member.user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(ClubMemberORM(
                club_id=club_id,
                user_id=member.user_id,
                status=member.status,
                joined_at=member.joined_at,
            ))
            s.commit()
            return True

    def set_member_status(self, club_id: int, user_id: int, status: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(ClubMemberORM)
                .where(
                    ClubMemberORM.club_id == club_id,
                    ClubMemberORM.user_id == user_id,
                )
                .values(status=status)
            )
            s.commit()
            return res.rowcount > 0

    def is_active_member(self, club_id: int, user_id: int) -> bool:
        with self.Session() as s:
            return s.scalars(
                select(ClubMemberORM).where(
                    ClubMemberORM.club_id == club_id,
                    ClubMemberORM.user_id == user_id,
                    ClubMemberORM.status == "active",
                )
            ).first() is not None
