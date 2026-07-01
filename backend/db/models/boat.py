"""Boat catalog table + standing crew membership."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class BoatORM(Base):
    __tablename__ = "boats"

    boat_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="")
    sail_number: Mapped[str] = mapped_column(String, default="")
    # Free-text club name (legacy). Kept in dual-read alongside ``club_id``
    # until the UI migrates; ``club_id`` is the structured reference.
    club: Mapped[str] = mapped_column(String, default="")
    club_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    loa_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Legacy informal skipper list; superseded by ``members`` (boat_members).
    # Kept for dual-read during migration.
    skippers: Mapped[list] = mapped_column(JSON, default=list)
    photos: Mapped[dict] = mapped_column(JSON, default=dict)
    cert_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mbsa_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    links: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(String, default="")
    polar: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    members: Mapped[list["BoatMemberORM"]] = relationship(
        back_populates="boat", cascade="all, delete-orphan"
    )


class BoatMemberORM(Base):
    """Standing crew of a boat (its persistent roster + management rights) —
    distinct from ``session_crew`` (who was actually aboard on a given outing).
    ``role`` is one of owner|skipper|crew|viewer; owner/skipper can manage the
    boat and its members."""

    __tablename__ = "boat_members"
    __table_args__ = (UniqueConstraint("boat_id", "user_id", name="uq_boat_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.boat_id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String, default="crew")  # owner|skipper|crew|viewer
    created_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    boat: Mapped["BoatORM"] = relationship(back_populates="members")
