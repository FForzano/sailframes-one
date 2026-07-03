"""SQL club repository (+ membership via ``user_clubs``). Reads return
``ClubORM`` (members embedded via ``to_dict``); membership ops take explicit
ids. Ownership is no longer a column — it's the scoped ``club_admin`` role."""

import uuid
from typing import Optional

from sqlalchemy import select, update

from ...db.models import ClubORM, UserClubORM


class SqlClubRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[ClubORM]:
        with self.Session() as s:
            return list(s.scalars(select(ClubORM)).all())

    def get(self, club_id: uuid.UUID) -> Optional[ClubORM]:
        with self.Session() as s:
            return s.get(ClubORM, club_id)

    def create(self, data: dict) -> ClubORM:
        with self.Session() as s:
            orm = ClubORM(**{k: v for k, v in data.items() if k != "members"})
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get(new_id)

    def add_member(self, club_id: uuid.UUID, *, user_id: uuid.UUID,
                   status: str = "invited") -> bool:
        with self.Session() as s:
            exists = s.scalars(
                select(UserClubORM).where(
                    UserClubORM.club_id == club_id,
                    UserClubORM.user_id == user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(UserClubORM(club_id=club_id, user_id=user_id, status=status))
            s.commit()
            return True

    def set_member_status(self, club_id: uuid.UUID, user_id: uuid.UUID, status: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(UserClubORM)
                .where(UserClubORM.club_id == club_id, UserClubORM.user_id == user_id)
                .values(status=status)
            )
            s.commit()
            return res.rowcount > 0

    def is_active_member(self, club_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        with self.Session() as s:
            return s.scalars(
                select(UserClubORM).where(
                    UserClubORM.club_id == club_id,
                    UserClubORM.user_id == user_id,
                    UserClubORM.status == "active",
                )
            ).first() is not None
