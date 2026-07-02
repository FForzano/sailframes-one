"""Group tables: free social groupings, independent of clubs and boats.

Speculare to ``ClubORM``/``ClubMemberORM`` in ``rbac.py``. Plain membership
(``group_members``) feeds the visibility filter; ``role`` on the membership
(``admin|member``) governs who may manage the group — there is no single-owner
column (a group can have several admins). ``created_by`` records the author.
"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class GroupORM(Base):
    __tablename__ = "groups"
    __wire_children__ = {"members": "members"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Author of the group (informational; management is by admin membership).
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Inherited by sessions shared with this group (private|group|club|public).
    default_session_visibility: Mapped[str] = mapped_column(String, default="private")
    created_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    members: Mapped[list["GroupMemberORM"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", lazy="selectin"
    )


class GroupMemberORM(Base):
    """Plain group membership used by the visibility filter. ``role`` (admin|
    member) governs management rights; ``status`` (invited|active) the join
    lifecycle."""

    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)
    __wire_exclude__ = ("id", "group_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String, default="member")  # admin | member
    status: Mapped[str] = mapped_column(String, default="active")  # invited | active
    joined_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    group: Mapped["GroupORM"] = relationship(back_populates="members")
