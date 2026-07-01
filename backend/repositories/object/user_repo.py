"""Object-storage user repository — ``meta/users.json``.

The password hash is persisted inside the JSON record but is never placed on
the returned ``User`` domain object (that model has no such field), so it can't
leak through an endpoint that serialises a ``User``.

No transactions: email-uniqueness on ``create`` is best-effort (read-modify-
write). Acceptable at single-club / fleet scale; Postgres enforces it hard.
"""

from typing import Optional

from ... import domain
from ...storage import BlobStore
from ..base import UserRepo
from ._common import USERS_INDEX_KEY, load_index, next_int_id


def _to_user(rec: dict) -> domain.User:
    # Build explicitly so ``password_hash`` never rides along on the domain obj.
    return domain.User(
        id=rec.get("id"),
        email=rec.get("email"),
        name=rec.get("name"),
        is_active=rec.get("is_active", True),
        is_superadmin=rec.get("is_superadmin", False),
        created_at=rec.get("created_at"),
    )


class ObjectUserRepo(UserRepo):
    def __init__(self, blob: BlobStore):
        self.blob = blob

    def _load(self) -> list[dict]:
        return load_index(self.blob, USERS_INDEX_KEY).get("users", [])

    def _save(self, users: list[dict]) -> None:
        self.blob.put_json(USERS_INDEX_KEY, {"users": users})

    def list(self) -> list[domain.User]:
        return [_to_user(r) for r in self._load()]

    def get_by_id(self, user_id: int) -> Optional[domain.User]:
        for r in self._load():
            if int(r.get("id") or 0) == int(user_id):
                return _to_user(r)
        return None

    def get_by_email(self, email: str) -> Optional[domain.User]:
        for r in self._load():
            if (r.get("email") or "").lower() == email.lower():
                return _to_user(r)
        return None

    def get_password_hash_by_email(self, email: str) -> Optional[str]:
        for r in self._load():
            if (r.get("email") or "").lower() == email.lower():
                return r.get("password_hash")
        return None

    def create(self, user: domain.User, password_hash: Optional[str]) -> domain.User:
        users = self._load()
        if any((r.get("email") or "").lower() == user.email.lower() for r in users):
            raise ValueError(f"User already exists: {user.email}")
        new_id = user.id or next_int_id(users)
        rec = {
            "id": new_id,
            "email": user.email,
            "password_hash": password_hash,
            "name": user.name,
            "is_active": user.is_active,
            "is_superadmin": user.is_superadmin,
            "created_at": user.created_at,
        }
        users.append(rec)
        self._save(users)
        return _to_user(rec)
