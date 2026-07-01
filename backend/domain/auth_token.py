"""Refresh-token domain model.

One row per issued refresh token. Rotation chains tokens by ``family_id`` (all
tokens descended from a single login) and ``prev_id`` (the token this one
replaced). Reuse of an already-rotated token revokes the whole family. Only the
``token_hash`` is ever stored — never the opaque token value itself.
"""

from typing import Optional

from .base import DomainModel


class AuthRefreshToken(DomainModel):
    id: Optional[int] = None
    user_id: int
    token_hash: str
    family_id: str
    prev_id: Optional[int] = None
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    revoked_at: Optional[str] = None
    user_agent: Optional[str] = None
