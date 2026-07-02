"""SQL club repository (+ membership). Reads return ``ClubORM`` (members
embedded via ``to_dict``); membership ops take explicit ids."""

from typing import Optional

from sqlalchemy import select, update

from ...db.models import ClubORM, ClubMemberORM


class SqlClubRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[ClubORM]:
        with self.Session() as s:
            return list(s.scalars(select(ClubORM)).all())

    def get(self, club_id: int) -> Optional[ClubORM]:
        with self.Session() as s:
            return s.get(ClubORM, club_id)

    def create(self, data: dict) -> ClubORM:
        with self.Session() as s:
            orm = ClubORM(
                name=data["name"],
                owner_user_id=data.get("owner_user_id"),
                default_session_visibility=data.get("default_session_visibility") or "private",
                created_at=data.get("created_at"),
            )
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get(new_id)

    def add_member(self, club_id: int, *, user_id: int, status: str = "active",
                   joined_at: Optional[str] = None) -> bool:
        with self.Session() as s:
            exists = s.scalars(
                select(ClubMemberORM).where(
                    ClubMemberORM.club_id == club_id,
                    ClubMemberORM.user_id == user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(ClubMemberORM(club_id=club_id, user_id=user_id, status=status, joined_at=joined_at))
            s.commit()
            return True

    def set_member_status(self, club_id: int, user_id: int, status: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(ClubMemberORM)
                .where(ClubMemberORM.club_id == club_id, ClubMemberORM.user_id == user_id)
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
