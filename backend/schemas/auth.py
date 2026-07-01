"""Auth request DTOs.

``email`` is a plain ``str`` (not pydantic ``EmailStr``) to avoid pulling in the
``email-validator`` dependency; the router does a light format check.
"""

from typing import Optional

from pydantic import BaseModel


class RegisterModel(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginModel(BaseModel):
    email: str
    password: str
