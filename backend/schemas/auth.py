"""Auth request DTOs.

``email`` is a plain ``str`` (not pydantic ``EmailStr``) to avoid pulling in the
``email-validator`` dependency; the router does a light format check.
"""

from typing import Optional

from pydantic import BaseModel


class RegisterModel(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    terms_and_conditions: bool = False


class LoginModel(BaseModel):
    email: str
    password: str


class ChangePasswordModel(BaseModel):
    current_password: str
    new_password: str


class RefreshModel(BaseModel):
    """Body for /auth/refresh and /auth/logout when the caller has no
    cookie jar to rely on (native clients) — the refresh token travels in
    the body instead. Web clients omit this; the cookie takes precedence
    when both are present."""

    refresh_token: Optional[str] = None
