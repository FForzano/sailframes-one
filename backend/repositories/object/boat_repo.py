"""Object-storage boat catalog repository — ``{DATA_PREFIX}/boats.json``.

Standing-crew membership lives **inside** each boat record (a ``members`` list),
mirroring how the SQL backend keeps a ``boat_members`` table. Best-effort, no
transactions.
"""

from typing import Optional

from ... import domain
from ...storage import BlobStore
from ..base import BoatRepo
from ._common import load_index


class ObjectBoatRepo(BoatRepo):
    def __init__(self, blob: BlobStore, data_prefix: str):
        self.blob = blob
        self.key = f"{data_prefix}/boats.json"

    def _load(self) -> dict:
        return load_index(self.blob, self.key) or {"boats": []}

    def _save(self, data: dict) -> None:
        self.blob.put_json(self.key, data)

    def list(self) -> list[domain.Boat]:
        return [domain.Boat.from_dict(b) for b in self._load().get("boats", [])]

    def get(self, boat_id: str) -> Optional[domain.Boat]:
        for b in self.list():
            if b.boat_id == boat_id:
                return b
        return None

    def save(self, boat: domain.Boat) -> domain.Boat:
        data = self._load()
        items = data.get("boats", [])
        for i, b in enumerate(items):
            if b.get("boat_id") == boat.boat_id:
                # Preserve existing members: save() carries the full boat, but
                # membership is managed through the dedicated member methods.
                merged = boat.to_dict()
                if "members" not in boat.model_fields_set:
                    merged["members"] = b.get("members", [])
                items[i] = merged
                break
        else:
            items.append(boat.to_dict())
        data["boats"] = items
        self._save(data)
        return boat

    def delete(self, boat_id: str) -> bool:
        data = self._load()
        items = data.get("boats", [])
        new_items = [b for b in items if b.get("boat_id") != boat_id]
        if len(new_items) == len(items):
            return False
        data["boats"] = new_items
        self._save(data)
        return True

    # --- standing crew ---

    def add_member(self, boat_id: str, member: domain.BoatMember) -> bool:
        data = self._load()
        for b in data.get("boats", []):
            if b.get("boat_id") == boat_id:
                members = b.setdefault("members", [])
                if any(int(m.get("user_id")) == int(member.user_id) for m in members):
                    return False
                members.append(member.to_dict())
                self._save(data)
                return True
        return False

    def remove_member(self, boat_id: str, user_id: int) -> bool:
        data = self._load()
        for b in data.get("boats", []):
            if b.get("boat_id") == boat_id:
                members = b.get("members", [])
                new_members = [m for m in members if int(m.get("user_id")) != int(user_id)]
                if len(new_members) == len(members):
                    return False
                b["members"] = new_members
                self._save(data)
                return True
        return False

    def set_member_role(self, boat_id: str, user_id: int, role: str) -> bool:
        data = self._load()
        for b in data.get("boats", []):
            if b.get("boat_id") == boat_id:
                for m in b.get("members", []):
                    if int(m.get("user_id")) == int(user_id):
                        m["role"] = role
                        self._save(data)
                        return True
        return False

    def list_members(self, boat_id: str) -> "list[domain.BoatMember]":
        for b in self._load().get("boats", []):
            if b.get("boat_id") == boat_id:
                return [domain.BoatMember.from_dict(m) for m in b.get("members", [])]
        return []

    def is_member(self, boat_id: str, user_id: int, roles: "Optional[list[str]]" = None) -> bool:
        for b in self._load().get("boats", []):
            if b.get("boat_id") == boat_id:
                for m in b.get("members", []):
                    if int(m.get("user_id")) == int(user_id):
                        return roles is None or m.get("role") in roles
        return False
