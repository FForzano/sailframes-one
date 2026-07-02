"""SQL user repository. Reads return ``UserORM`` (``to_dict()`` drops the
password hash); the hash is read only for login via a dedicated method."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from ...db.models import UserORM


class SqlUserRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[UserORM]:
        with self.Session() as s:
            return list(s.scalars(select(UserORM)).all())

    def get_by_id(self, user_id: int) -> Optional[UserORM]:
        with self.Session() as s:
            return s.get(UserORM, user_id)

    def get_by_email(self, email: str) -> Optional[UserORM]:
        with self.Session() as s:
            return self._by_email(s, email)

    def get_password_hash_by_email(self, email: str) -> Optional[str]:
        with self.Session() as s:
            orm = self._by_email(s, email)
            return orm.password_hash if orm else None

    def create(self, *, email: str, password_hash: Optional[str], name: Optional[str] = None,
               is_active: bool = True, is_superadmin: bool = False,
               created_at: Optional[str] = None) -> UserORM:
        with self.Session() as s:
            if self._by_email(s, email) is not None:
                raise ValueError(f"User already exists: {email}")
            orm = UserORM(
                email=email,
                password_hash=password_hash,
                name=name,
                is_active=is_active,
                is_superadmin=is_superadmin,
                created_at=created_at or datetime.now(timezone.utc).isoformat(),
            )
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get_by_id(new_id)

    @staticmethod
    def _by_email(s, email: str) -> Optional[UserORM]:
        return s.scalars(
            select(UserORM).where(func.lower(UserORM.email) == email.lower())
        ).first()
