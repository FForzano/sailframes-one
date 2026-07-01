#!/usr/bin/env python3
"""One-shot, idempotent migration: legacy ``Boat.skippers`` -> ``boat_members``.

Phase 2 replaces the informal ``skippers`` list (``[{name, photo}, …]``, no
guaranteed schema) with structured standing crew (``boat_members``, keyed on a
real ``user_id``). This script resolves each skipper entry to an account and,
where it can, adds it as a ``skipper`` boat member.

Design notes (per docs/user_plan.md / user_plan_next_phases.md):
- **Never creates accounts.** Skipper entries carry only a free-text ``name``
  (and optional photo); one is resolvable only if it carries an ``email`` (or a
  ``name`` that is itself an email) matching an existing user. Unresolvable
  entries are left untouched in ``skippers`` (kept in dual-read) and skipped.
- **Backend-agnostic.** Runs through ``get_repos()`` so it behaves identically
  on the object (blob JSON) and Postgres backends — pick the backend via
  ``SAILFRAMES_METADATA_BACKEND`` exactly as the API does.
- **Idempotent.** ``add_member`` is a no-op when the user is already a member,
  so re-running is safe.

Usage:
    SAILFRAMES_METADATA_BACKEND=object   python scripts/migrate_boat_members.py [--dry-run]
    SAILFRAMES_METADATA_BACKEND=postgres python scripts/migrate_boat_members.py [--dry-run]
"""

import argparse
import pathlib
import sys

# web/ on sys.path so ``import api...`` works regardless of CWD (mirrors
# web/api/alembic/env.py).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "web"))


def _looks_like_email(value: str) -> bool:
    return isinstance(value, str) and "@" in value and "." in value.split("@")[-1]


def _skipper_email(entry) -> str | None:
    """Best-effort email for a legacy skipper entry, or ``None``."""
    if isinstance(entry, dict):
        email = entry.get("email")
        if _looks_like_email(email or ""):
            return email.strip().lower()
        name = entry.get("name")
        if _looks_like_email(name or ""):
            return name.strip().lower()
    elif _looks_like_email(entry or ""):
        return entry.strip().lower()
    return None


def migrate(dry_run: bool = False) -> None:
    from datetime import datetime, timezone

    from api import domain
    from api.repositories import get_repos, select_metadata_backend

    repos = get_repos()
    now = datetime.now(timezone.utc).isoformat()

    print(f"Backend: {select_metadata_backend()}")
    added = skipped_unresolved = skipped_existing = 0

    for boat in repos.boats.list():
        for entry in boat.skippers or []:
            email = _skipper_email(entry)
            label = entry.get("name") if isinstance(entry, dict) else entry
            if not email:
                skipped_unresolved += 1
                print(f"  [skip] {boat.boat_id}: unresolvable skipper {label!r} (no email)")
                continue
            user = repos.users.get_by_email(email)
            if user is None:
                skipped_unresolved += 1
                print(f"  [skip] {boat.boat_id}: no account for {email} (not creating one)")
                continue
            if repos.boats.is_member(boat.boat_id, user.id):
                skipped_existing += 1
                continue
            if dry_run:
                print(f"  [would add] {boat.boat_id}: user {user.id} ({email}) as skipper")
                added += 1
                continue
            ok = repos.boats.add_member(boat.boat_id, domain.BoatMember(
                user_id=user.id, role="skipper", created_at=now,
            ))
            if ok:
                added += 1
                print(f"  [added] {boat.boat_id}: user {user.id} ({email}) as skipper")
            else:
                skipped_existing += 1

    verb = "would add" if dry_run else "added"
    print(
        f"\nDone. {verb}={added} "
        f"already-member={skipped_existing} unresolved={skipped_unresolved}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
