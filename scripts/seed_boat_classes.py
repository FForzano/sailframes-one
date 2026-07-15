#!/usr/bin/env python3
"""Seed/update ``boat_classes`` from the official RYA Portsmouth Yardstick
list (data/rya_py_list_2026.json — extracted from the RYA's published
"PN List 2026" PDF, https://www.rya.org.uk, Dinghy + Multi sections; the
Limited Data / Experimental Numbers rows are included too since they still
carry a stable RYA Class ID and starting PY number).

Only the fields the RYA list actually publishes are touched: ``name``,
``rya_class_id``, ``crew_size``, ``rig_type``, ``spinnaker_type`` and
``py_rating`` (hull_type is derived from the Dinghy/Multi section split).
``description``/``logo_id``/``loa_m``/``beam_m``/``sail_area_sqm`` are never
touched — those are admin-filled extras outside the RYA list's scope, and
this script must not clobber whatever an admin has already entered there.

Idempotent and safe to re-run every time the RYA republishes the list:
matches existing rows by ``rya_class_id`` first, falling back to an
case-insensitive exact ``name`` match for a class created locally before it
had an RYA ID (that class gets linked, not duplicated). Anything left
unmatched is created.

Run with the backend environment configured (DB reachable), e.g. inside the
backend container:

    python scripts/seed_boat_classes.py            # apply
    python scripts/seed_boat_classes.py --dry-run  # preview only
"""

import argparse
import json
import sys
from pathlib import Path

from backend.repositories import get_repos

DATA_FILE = Path(__file__).parent / "data" / "rya_py_list_2026.json"
RYA_FIELDS = ("name", "rya_class_id", "crew_size", "rig_type", "spinnaker_type",
              "py_rating", "hull_type")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview changes, write nothing")
    args = parser.parse_args()

    rows = json.loads(DATA_FILE.read_text())
    repos = get_repos()
    existing = repos.boats.list_classes(limit=10_000)
    by_rya_id = {c.rya_class_id: c for c in existing if c.rya_class_id is not None}
    by_name = {c.name.strip().lower(): c for c in existing}

    created = updated = unchanged = 0
    for row in rows:
        match = by_rya_id.get(row["rya_class_id"]) or by_name.get(row["name"].strip().lower())
        if match is None:
            print(f"CREATE  {row['name']!r} (RYA ID {row['rya_class_id']})")
            if not args.dry_run:
                repos.boats.create_class({k: row[k] for k in RYA_FIELDS})
            created += 1
            continue

        changes = {k: row[k] for k in RYA_FIELDS if getattr(match, k) != row[k]}
        if not changes:
            unchanged += 1
            continue
        print(f"UPDATE  {match.name!r} -> {changes}")
        if not args.dry_run:
            repos.boats.update_class(match.id, changes)
        updated += 1

    print(f"\n{created} created, {updated} updated, {unchanged} unchanged"
          f"{' (dry run — nothing written)' if args.dry_run else ''}")


if __name__ == "__main__":
    sys.exit(main())
