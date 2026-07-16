"""App-config: a single superadmin-editable settings row, currently just the
minimum required native app version per platform (see docs/native-apps.md,
"Forcing a native update"). GET is intentionally public/unauthenticated —
the native app must be able to check it before login, since a logged-out
user on a blocked version should never even reach the login screen.
"""

from fastapi import APIRouter, Request

from ..auth import require_superadmin, verify_csrf
from ..schemas import AppConfigUpdateModel
from ._common import repos

router = APIRouter(prefix="/api", tags=["app-config"])


@router.get("/app-config")
def get_app_config():
    config = repos.app_config.get()
    return (
        config.to_dict()
        if config
        else {"min_native_version_android": None, "min_native_version_ios": None}
    )


@router.patch("/app-config")
def update_app_config(body: AppConfigUpdateModel, request: Request):
    verify_csrf(request)
    require_superadmin(request)
    updated = repos.app_config.update(body.model_dump())
    return updated.to_dict()
