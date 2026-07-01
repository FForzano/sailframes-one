"""Password hashing.

Argon2id (via ``argon2-cffi``) with secure library defaults. The stored string
is Argon2's own PHC-encoded form (``$argon2id$v=19$m=...,t=...,p=...$salt$hash``),
which carries its parameters inline, so ``verify_password`` needs no external
config to check a hash.
"""

from argon2 import PasswordHasher

# Thread-safe; secure library defaults. Reused across calls.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    if not encoded:
        return False
    try:
        return _hasher.verify(encoded, password)
    except Exception:
        return False
