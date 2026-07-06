"""Session tables: ``sessions`` + crew/media/stats children.

A session is one boat's participation in an activity. It carries no
source/device columns — a session can receive data from several devices at
once (the E1 on the boat + a smartwatch per crew member), so that relation
lives in ``session_uploads`` (see ``ingest.py``). ``status`` is the aggregate
of the linked uploads' statuses. Raw 10Hz series stay in object storage
(referenced by ``session_streams.data_ref``); the DB indexes metadata only.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, CreatedAtMixin, UUIDPKMixin, enum_check

SESSION_STATUSES = ("pending", "processing", "processed", "failed")
SESSION_SAILING_ROLES = ("skipper", "crew", "guest")


class SessionORM(UUIDPKMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (enum_check("status", SESSION_STATUSES),)

    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # RESTRICT: a boat with recorded sessions cannot be hard-deleted.
    boat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("boats.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Derived/aggregated from the statuses of the linked session_uploads.
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")


class SessionCrewORM(UUIDPKMixin, CreatedAtMixin, Base):
    """Who was actually aboard for THIS outing — distinct from the default in
    ``user_boats.default_sailing_role``. The user need not be linked to the
    boat in ``user_boats`` (e.g. occasional guest)."""

    __tablename__ = "session_crew"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id"),
        enum_check("sailing_role", SESSION_SAILING_ROLES),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sailing_role: Mapped[str] = mapped_column(String, nullable=False, default="crew")


class SessionPhotoORM(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "session_photos"
    __table_args__ = (UniqueConstraint("session_id", "image_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), nullable=False
    )
    # Who uploaded it (can be a crew member).
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SessionVideoORM(UUIDPKMixin, CreatedAtMixin, Base):
    """Videos go through ``files`` (not ``images``) — the generic non-image
    blob entity already used for boats.cert_id/mbsa_id."""

    __tablename__ = "session_videos"
    __table_args__ = (UniqueConstraint("session_id", "file_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SessionStatsORM(Base):
    """1:1 aggregate stats — PK is the session itself, no surrogate id."""

    __tablename__ = "session_stats"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    distance_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_speed_kts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_speed_kts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Require wind data (onboard or wind_observations).
    avg_polar_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_polar_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
