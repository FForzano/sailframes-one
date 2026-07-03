"""Media blobs: ``images`` and ``files``.

Both are thin pointers to S3/MinIO objects (``ref``) with a lifecycle status.
Every other table that needs a picture (profile image, club logo, boat photos,
session photos) references ``images``; generic non-image blobs (boat
certificates, session videos) reference ``files``. Access is always mediated
by the parent resource — these rows carry no permission level of their own
(see docs/api-project.md, "Media").
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, CreatedAtMixin, UUIDPKMixin, enum_check

MEDIA_STATUSES = ("uploaded", "processed", "deleted")


class ImageORM(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "images"
    __table_args__ = (enum_check("status", MEDIA_STATUSES),)

    ref: Mapped[str] = mapped_column(String, nullable=False)  # S3/MinIO object key
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class FileORM(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "files"
    __table_args__ = (enum_check("status", MEDIA_STATUSES),)

    ref: Mapped[str] = mapped_column(String, nullable=False)  # S3/MinIO object key
    status: Mapped[str] = mapped_column(String, nullable=False, default="uploaded")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
