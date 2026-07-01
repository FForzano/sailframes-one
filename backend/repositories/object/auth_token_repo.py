"""Object-storage refresh-token repository — ``meta/auth_tokens.json``.

Best-effort (no transactions): reuse-detection and family revocation are
read-modify-write on a JSON list. Acceptable at fleet scale; Postgres is
transactional. Only token *hashes* are stored.
"""

from typing import Optional

from ... import domain
from ...storage import BlobStore
from ..base import AuthTokenRepo
from ._common import AUTH_TOKENS_INDEX_KEY, load_index, next_int_id


class ObjectAuthTokenRepo(AuthTokenRepo):
    def __init__(self, blob: BlobStore):
        self.blob = blob

    def _load(self) -> list[dict]:
        return load_index(self.blob, AUTH_TOKENS_INDEX_KEY).get("tokens", [])

    def _save(self, tokens: list[dict]) -> None:
        self.blob.put_json(AUTH_TOKENS_INDEX_KEY, {"tokens": tokens})

    def create(self, token: domain.AuthRefreshToken) -> domain.AuthRefreshToken:
        tokens = self._load()
        new_id = token.id or next_int_id(tokens)
        rec = token.to_dict()
        rec["id"] = new_id
        tokens.append(rec)
        self._save(tokens)
        return domain.AuthRefreshToken.from_dict(rec)

    def get_by_hash(self, token_hash: str) -> Optional[domain.AuthRefreshToken]:
        for r in self._load():
            if r.get("token_hash") == token_hash:
                return domain.AuthRefreshToken.from_dict(r)
        return None

    def revoke(self, token_id: int, revoked_at: str) -> None:
        tokens = self._load()
        for r in tokens:
            if int(r.get("id") or 0) == int(token_id) and not r.get("revoked_at"):
                r["revoked_at"] = revoked_at
        self._save(tokens)

    def revoke_family(self, family_id: str, revoked_at: str) -> None:
        tokens = self._load()
        for r in tokens:
            if r.get("family_id") == family_id and not r.get("revoked_at"):
                r["revoked_at"] = revoked_at
        self._save(tokens)
