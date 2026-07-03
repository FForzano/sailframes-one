"""RBAC tables: roles, permissions, and their join tables.

Full role-based access control: permissions are assigned to roles
(``role_permissions``), roles are granted to users optionally scoped to a club
(``user_roles.scope_club_id`` NULL = global). Superadmin is a flag on ``users``
(bypasses everything), not a role row. See ``backend/auth`` for how these are
evaluated and seeded.
"""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, UUIDPKMixin


class RoleORM(UUIDPKMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    permissions: Mapped[list["RolePermissionORM"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class PermissionORM(UUIDPKMixin, Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class RolePermissionORM(UUIDPKMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE")
    )

    role: Mapped["RoleORM"] = relationship(back_populates="permissions")


class UserRoleORM(UUIDPKMixin, Base):
    __tablename__ = "user_roles"
    # nulls_not_distinct so two identical global grants (scope NULL) collide.
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "scope_club_id", postgresql_nulls_not_distinct=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    # NULL scope = global grant; otherwise the role applies within this club.
    scope_club_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["UserORM"] = relationship(back_populates="roles")  # noqa: F821
