"""Session (manifest metadata) table.

Only manifest-level metadata; the bulk sensor payloads always stay in the blob
store. Device-sourced sessions (``source="device"``) are unique per
(device_id, date), mirroring the object layout — enforced by a partial unique
index (see migration ``0006_manual_sessions``) so it only applies when both
columns are set.

⚠️ ``date`` is a **folder slug** (``YYYYMMDD`` or ``session_NNN``), not a
calendar date — it is the per-outing identifier for device-sourced sessions. Do
not compute on it. Phase 5 adds the privacy/attribution columns + the
``session_crew`` table (the actual crew of the outing, distinct from a boat's
standing ``boat_members``).

A **manual** session (``source="manual"``) has no device: it is created by
hand (boat + crew) and gets its data from an uploaded GPX track instead of the
CSV ingest pipeline. It has no ``device_id``/``date``, so it's addressed by the
surrogate ``id`` PK instead, and its processed data lives under
``processed/manual/{id}/`` (see ``backend/services/gpx_processing.py``).
``processing_status`` tracks that async GPX-parse-and-analyze job.
"""

from typing import Any, Optional

from sqlalchemy import (
    ForeignKey,
    Integer,
    JSON,
    Boolean,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class SessionORM(Base):
    __tablename__ = "sessions"
    __wire_children__ = {"crew": "crew"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    boat: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sensors: Mapped[Any] = mapped_column(JSON, nullable=True)
    has_video: Mapped[bool] = mapped_column(Boolean, default=False)
    has_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    trim: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # --- Phase 5: privacy + attribution ---
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    boat_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    visibility: Mapped[str] = mapped_column(String, default="private")
    club_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    regatta_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    race_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Manual/GPX sessions ---
    source: Mapped[str] = mapped_column(String, default="device")  # device | manual
    processing_status: Mapped[str] = mapped_column(String, default="ready")
    # pending | processing | ready | failed (manual only; device sessions are
    # already processed by the CSV ingest pipeline by the time they're visible)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    crew: Mapped[list["SessionCrewORM"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        d = super().to_dict()
        if d.get("sensors") is None:
            d["sensors"] = []  # wire expects a list, never null
        return d


class SessionCrewORM(Base):
    """A crew slot on one session. Exactly one of ``user_id`` / ``guest_name``
    is set (a registered user, or a guest without an account)."""

    __tablename__ = "session_crew"
    __wire_exclude__ = ("id", "session_id")

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    guest_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    boat_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    session: Mapped["SessionORM"] = relationship(back_populates="crew")
