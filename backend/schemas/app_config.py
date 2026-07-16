"""App-config request DTO — see db/models/app_config.py."""

from typing import Optional

from pydantic import BaseModel


class AppConfigUpdateModel(BaseModel):
    # "x.y.z", or null to clear the gate for that platform (no minimum
    # enforced). Separate fields since Android/iOS ship independently.
    min_native_version_android: Optional[str] = None
    min_native_version_ios: Optional[str] = None
