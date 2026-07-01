"""SQL refresh-token repository (rotation + reuse detection)."""

from typing import Optional

from sqlalchemy import select, update

from ... import domain
from ...db.models import AuthRefreshTokenORM
from ..base import AuthTokenRepo
from . import _mappers as M


class SqlAuthTokenRepo(AuthTokenRepo):
    def __init__(self, session_factory):
        self.Session = session_factory

    def create(self, token: domain.AuthRefreshToken) -> domain.AuthRefreshToken:
        with self.Session() as s:
            orm = AuthRefreshTokenORM(
                user_id=token.user_id,
                token_hash=token.token_hash,
                family_id=token.family_id,
                prev_id=token.prev_id,
                issued_at=token.issued_at,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
                user_agent=token.user_agent,
            )
            s.add(orm)
            s.commit()
            return M.token_to_domain(orm)

    def get_by_hash(self, token_hash: str) -> Optional[domain.AuthRefreshToken]:
        with self.Session() as s:
            orm = s.scalars(
                select(AuthRefreshTokenORM).where(
                    AuthRefreshTokenORM.token_hash == token_hash
                )
            ).first()
            return M.token_to_domain(orm) if orm else None

    def revoke(self, token_id: int, revoked_at: str) -> None:
        with self.Session() as s:
            s.execute(
                update(AuthRefreshTokenORM)
                .where(
                    AuthRefreshTokenORM.id == token_id,
                    AuthRefreshTokenORM.revoked_at.is_(None),
                )
                .values(revoked_at=revoked_at)
            )
            s.commit()

    def revoke_family(self, family_id: str, revoked_at: str) -> None:
        with self.Session() as s:
            s.execute(
                update(AuthRefreshTokenORM)
                .where(
                    AuthRefreshTokenORM.family_id == family_id,
                    AuthRefreshTokenORM.revoked_at.is_(None),
                )
                .values(revoked_at=revoked_at)
            )
            s.commit()
