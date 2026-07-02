"""SQL group repository (+ membership). Speculare to ``SqlClubRepo``."""

from typing import Optional

from sqlalchemy import select, update

from ...db.models import GroupORM, GroupMemberORM


class SqlGroupRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[GroupORM]:
        with self.Session() as s:
            return list(s.scalars(select(GroupORM)).all())

    def get(self, group_id: int) -> Optional[GroupORM]:
        with self.Session() as s:
            return s.get(GroupORM, group_id)

    def create(self, data: dict) -> GroupORM:
        with self.Session() as s:
            orm = GroupORM(
                name=data["name"],
                description=data.get("description"),
                created_by=data.get("created_by"),
                default_session_visibility=data.get("default_session_visibility") or "private",
                created_at=data.get("created_at"),
            )
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get(new_id)

    def add_member(self, group_id: int, *, user_id: int, role: str = "member",
                   status: str = "active", joined_at: Optional[str] = None) -> bool:
        with self.Session() as s:
            exists = s.scalars(
                select(GroupMemberORM).where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(GroupMemberORM(group_id=group_id, user_id=user_id, role=role,
                                 status=status, joined_at=joined_at))
            s.commit()
            return True

    def set_member_status(self, group_id: int, user_id: int, status: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(GroupMemberORM)
                .where(GroupMemberORM.group_id == group_id, GroupMemberORM.user_id == user_id)
                .values(status=status)
            )
            s.commit()
            return res.rowcount > 0

    def set_member_role(self, group_id: int, user_id: int, role: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(GroupMemberORM)
                .where(GroupMemberORM.group_id == group_id, GroupMemberORM.user_id == user_id)
                .values(role=role)
            )
            s.commit()
            return res.rowcount > 0

    def is_member(self, group_id: int, user_id: int) -> bool:
        with self.Session() as s:
            return s.scalars(
                select(GroupMemberORM).where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == user_id,
                    GroupMemberORM.status == "active",
                )
            ).first() is not None
