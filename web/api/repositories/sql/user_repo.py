"""SQL user repository. Password hash lives on the ORM row only."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from ... import domain
from ...db.models import UserORM
from ..base import UserRepo
from . import _mappers as M


class SqlUserRepo(UserRepo):
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[domain.User]:
        with self.Session() as s:
            return [M.user_to_domain(u) for u in s.scalars(select(UserORM)).all()]

    def get_by_id(self, user_id: int) -> Optional[domain.User]:
        with self.Session() as s:
            orm = s.get(UserORM, user_id)
            return M.user_to_domain(orm) if orm else None

    def get_by_email(self, email: str) -> Optional[domain.User]:
        with self.Session() as s:
            orm = self._by_email(s, email)
            return M.user_to_domain(orm) if orm else None

    def get_password_hash_by_email(self, email: str) -> Optional[str]:
        with self.Session() as s:
            orm = self._by_email(s, email)
            return orm.password_hash if orm else None

    def create(self, user: domain.User, password_hash: Optional[str]) -> domain.User:
        with self.Session() as s:
            if self._by_email(s, user.email) is not None:
                raise ValueError(f"User already exists: {user.email}")
            orm = UserORM(
                email=user.email,
                password_hash=password_hash,
                name=user.name,
                is_active=user.is_active,
                is_superadmin=user.is_superadmin,
                created_at=user.created_at or datetime.now(timezone.utc).isoformat(),
            )
            s.add(orm)
            s.commit()
            return M.user_to_domain(orm)

    @staticmethod
    def _by_email(s, email: str) -> Optional[UserORM]:
        return s.scalars(
            select(UserORM).where(func.lower(UserORM.email) == email.lower())
        ).first()
