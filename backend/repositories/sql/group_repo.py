"""SQL group repository (+ membership via ``user_groups``). Speculare to
``SqlClubRepo``; membership is soft-deleted (``deleted_at``), not statused."""

import uuid
from typing import Optional

from sqlalchemy import select, update

from ...db.models import GroupORM, UserGroupORM


class SqlGroupRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[GroupORM]:
        with self.Session() as s:
            return list(s.scalars(select(GroupORM)).all())

    def get(self, group_id: uuid.UUID) -> Optional[GroupORM]:
        with self.Session() as s:
            return s.get(GroupORM, group_id)

    def create(self, data: dict) -> GroupORM:
        with self.Session() as s:
            orm = GroupORM(**{k: v for k, v in data.items() if k != "members"})
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get(new_id)

    def add_member(self, group_id: uuid.UUID, *, user_id: uuid.UUID,
                   role: str = "member") -> bool:
        with self.Session() as s:
            exists = s.scalars(
                select(UserGroupORM).where(
                    UserGroupORM.group_id == group_id,
                    UserGroupORM.user_id == user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(UserGroupORM(group_id=group_id, user_id=user_id, role=role))
            s.commit()
            return True

    def set_member_role(self, group_id: uuid.UUID, user_id: uuid.UUID, role: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(UserGroupORM)
                .where(UserGroupORM.group_id == group_id, UserGroupORM.user_id == user_id)
                .values(role=role)
            )
            s.commit()
            return res.rowcount > 0

    def is_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        with self.Session() as s:
            return s.scalars(
                select(UserGroupORM).where(
                    UserGroupORM.group_id == group_id,
                    UserGroupORM.user_id == user_id,
                    UserGroupORM.deleted_at.is_(None),
                )
            ).first() is not None
