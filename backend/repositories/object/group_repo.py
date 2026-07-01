"""Object-storage group repository — ``meta/groups.json``.

Clone of ``ObjectClubRepo``: membership is nested inside each group record (the
visibility filter only ever needs it per-group). Best-effort, no transactions.
"""

from typing import Optional

from ... import domain
from ...storage import BlobStore
from ..base import GroupRepo
from ._common import GROUPS_INDEX_KEY, load_index, next_int_id


class ObjectGroupRepo(GroupRepo):
    def __init__(self, blob: BlobStore):
        self.blob = blob

    def _load(self) -> list[dict]:
        return load_index(self.blob, GROUPS_INDEX_KEY).get("groups", [])

    def _save(self, groups: list[dict]) -> None:
        self.blob.put_json(GROUPS_INDEX_KEY, {"groups": groups})

    def list(self) -> list[domain.Group]:
        return [domain.Group.from_dict(g) for g in self._load()]

    def get(self, group_id: int) -> Optional[domain.Group]:
        for g in self._load():
            if int(g.get("id") or 0) == int(group_id):
                return domain.Group.from_dict(g)
        return None

    def save(self, group: domain.Group) -> domain.Group:
        groups = self._load()
        if group.id is None:
            group.id = next_int_id(groups)
            groups.append(group.to_dict())
        else:
            for i, g in enumerate(groups):
                if int(g.get("id") or 0) == int(group.id):
                    groups[i] = group.to_dict()
                    break
            else:
                groups.append(group.to_dict())
        self._save(groups)
        return group

    def add_member(self, group_id: int, member: domain.GroupMember) -> bool:
        groups = self._load()
        for g in groups:
            if int(g.get("id") or 0) == int(group_id):
                members = g.setdefault("members", [])
                if any(int(m.get("user_id")) == int(member.user_id) for m in members):
                    return False
                members.append(member.to_dict())
                self._save(groups)
                return True
        return False

    def set_member_status(self, group_id: int, user_id: int, status: str) -> bool:
        groups = self._load()
        for g in groups:
            if int(g.get("id") or 0) == int(group_id):
                for m in g.get("members", []):
                    if int(m.get("user_id")) == int(user_id):
                        m["status"] = status
                        self._save(groups)
                        return True
        return False

    def set_member_role(self, group_id: int, user_id: int, role: str) -> bool:
        groups = self._load()
        for g in groups:
            if int(g.get("id") or 0) == int(group_id):
                for m in g.get("members", []):
                    if int(m.get("user_id")) == int(user_id):
                        m["role"] = role
                        self._save(groups)
                        return True
        return False

    def is_member(self, group_id: int, user_id: int) -> bool:
        for g in self._load():
            if int(g.get("id") or 0) == int(group_id):
                return any(
                    int(m.get("user_id")) == int(user_id) and m.get("status") == "active"
                    for m in g.get("members", [])
                )
        return False
