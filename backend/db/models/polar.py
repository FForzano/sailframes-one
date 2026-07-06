"""Polar performance points (``polar_points``).

Three granularities share the one table — exactly one owner FK is set:
``class_id`` + source=reference = published class curve (e.g. Seapilot);
``boat_id`` + source=empirical = historical aggregate across the boat's
sessions (``sample_count`` grows over time); ``session_id`` + source=empirical
= polar of a single outing. ``boat_id`` is not duplicated on session rows —
it is reachable via ``sessions.boat_id``.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, UUIDPKMixin, enum_check

POLAR_SOURCES = ("reference", "empirical")


class PolarPointORM(UUIDPKMixin, Base):
    __tablename__ = "polar_points"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(class_id, boat_id, session_id) = 1",
            name="owner_exactly_one",
        ),
        enum_check("source", POLAR_SOURCES),
    )

    class_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("boat_classes.id", ondelete="CASCADE"), nullable=True
    )
    boat_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("boats.id", ondelete="CASCADE"), nullable=True
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    twa_deg: Mapped[float] = mapped_column(Float, nullable=False)
    tws_kts: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kts: Mapped[float] = mapped_column(Float, nullable=False)
    vmg_kts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # mostly empirical
    sample_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # empirical only
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
