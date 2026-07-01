"""SQL group repository (+ membership). Clone of ``SqlClubRepo``."""

from typing import Optional

from sqlalchemy import select, update

from ... import domain
from ...db.models import GroupORM, GroupMemberORM
from ..base import GroupRepo
from . import _mappers as M


class SqlGroupRepo(GroupRepo):
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[domain.Group]:
        with self.Session() as s:
            return [M.group_to_domain(g) for g in s.scalars(select(GroupORM)).all()]

    def get(self, group_id: int) -> Optional[domain.Group]:
        with self.Session() as s:
            orm = s.get(GroupORM, group_id)
            return M.group_to_domain(orm) if orm else None

    def save(self, group: domain.Group) -> domain.Group:
        with self.Session() as s:
            orm = s.get(GroupORM, group.id) if group.id is not None else None
            if orm is None:
                orm = GroupORM(name=group.name)
                s.add(orm)
            orm.name = group.name
            orm.description = group.description
            orm.created_by = group.created_by
            orm.default_session_visibility = group.default_session_visibility
            orm.created_at = group.created_at
            s.commit()
            group.id = orm.id
            return group

    def add_member(self, group_id: int, member: domain.GroupMember) -> bool:
        with self.Session() as s:
            exists = s.scalars(
                select(GroupMemberORM).where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == member.user_id,
                )
            ).first()
            if exists is not None:
                return False
            s.add(GroupMemberORM(
                group_id=group_id,
                user_id=member.user_id,
                role=member.role,
                status=member.status,
                joined_at=member.joined_at,
            ))
            s.commit()
            return True

    def set_member_status(self, group_id: int, user_id: int, status: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(GroupMemberORM)
                .where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == user_id,
                )
                .values(status=status)
            )
            s.commit()
            return res.rowcount > 0

    def set_member_role(self, group_id: int, user_id: int, role: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(GroupMemberORM)
                .where(
                    GroupMemberORM.group_id == group_id,
                    GroupMemberORM.user_id == user_id,
                )
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
