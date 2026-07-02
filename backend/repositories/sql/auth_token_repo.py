"""SQL refresh-token repository (rotation + reuse detection). Returns
``AuthRefreshTokenORM`` rows; auth logic reads their attributes directly."""

from typing import Optional

from sqlalchemy import select, update

from ...db.models import AuthRefreshTokenORM


class SqlAuthTokenRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def create(self, *, user_id: int, token_hash: str, family_id: str,
               prev_id: Optional[int] = None, issued_at: Optional[str] = None,
               expires_at: Optional[str] = None, revoked_at: Optional[str] = None,
               user_agent: Optional[str] = None) -> AuthRefreshTokenORM:
        with self.Session() as s:
            orm = AuthRefreshTokenORM(
                user_id=user_id, token_hash=token_hash, family_id=family_id,
                prev_id=prev_id, issued_at=issued_at, expires_at=expires_at,
                revoked_at=revoked_at, user_agent=user_agent,
            )
            s.add(orm)
            s.commit()
            s.refresh(orm)
            s.expunge(orm)
            return orm

    def get_by_hash(self, token_hash: str) -> Optional[AuthRefreshTokenORM]:
        with self.Session() as s:
            return s.scalars(
                select(AuthRefreshTokenORM).where(AuthRefreshTokenORM.token_hash == token_hash)
            ).first()

    def revoke(self, token_id: int, revoked_at: str) -> None:
        with self.Session() as s:
            s.execute(
                update(AuthRefreshTokenORM)
                .where(AuthRefreshTokenORM.id == token_id, AuthRefreshTokenORM.revoked_at.is_(None))
                .values(revoked_at=revoked_at)
            )
            s.commit()

    def revoke_family(self, family_id: str, revoked_at: str) -> None:
        with self.Session() as s:
            s.execute(
                update(AuthRefreshTokenORM)
                .where(AuthRefreshTokenORM.family_id == family_id, AuthRefreshTokenORM.revoked_at.is_(None))
                .values(revoked_at=revoked_at)
            )
            s.commit()
