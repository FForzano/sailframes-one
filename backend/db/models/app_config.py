"""Singleton app-config row: a small set of superadmin-editable settings that
need to change without a redeploy — currently just the minimum required
native app version, per platform (see docs/native-apps.md, "Forcing a
native update"). There is always exactly one row (seeded by
``auth.seed.seed_app_config``); callers never create additional rows.
"""

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, TimestampMixin, UUIDPKMixin


class AppConfigORM(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "app_config"

    # "x.y.z" (matches the native app's versionName/CFBundleShortVersionString).
    # Installed versions below this are blocked with an "update required"
    # screen (frontend/src/components/native/NativeVersionGate.tsx). NULL =
    # no gate — the default, so this table existing never blocks anyone
    # until a superadmin explicitly sets a value. Android and iOS get
    # separate fields since their release cadences are independent (App
    # Store review can lag a same-day Play Store rollout by days).
    min_native_version_android: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    min_native_version_ios: Mapped[Optional[str]] = mapped_column(String, nullable=True)
