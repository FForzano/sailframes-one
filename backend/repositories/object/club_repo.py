"""Object-storage club repository — ``meta/clubs.json``.

Membership is stored nested inside each club record (the visibility filter only
ever needs it per-club). Best-effort, no transactions.
"""

from typing import Optional

from ... import domain
from ...storage import BlobStore
from ..base import ClubRepo
from ._common import CLUBS_INDEX_KEY, load_index, next_int_id


class ObjectClubRepo(ClubRepo):
    def __init__(self, blob: BlobStore):
        self.blob = blob

    def _load(self) -> list[dict]:
        return load_index(self.blob, CLUBS_INDEX_KEY).get("clubs", [])

    def _save(self, clubs: list[dict]) -> None:
        self.blob.put_json(CLUBS_INDEX_KEY, {"clubs": clubs})

    def list(self) -> list[domain.Club]:
        return [domain.Club.from_dict(c) for c in self._load()]

    def get(self, club_id: int) -> Optional[domain.Club]:
        for c in self._load():
            if int(c.get("id") or 0) == int(club_id):
                return domain.Club.from_dict(c)
        return None

    def save(self, club: domain.Club) -> domain.Club:
        clubs = self._load()
        if club.id is None:
            club.id = next_int_id(clubs)
            clubs.append(club.to_dict())
        else:
            for i, c in enumerate(clubs):
                if int(c.get("id") or 0) == int(club.id):
                    clubs[i] = club.to_dict()
                    break
            else:
                clubs.append(club.to_dict())
        self._save(clubs)
        return club

    def add_member(self, club_id: int, member: domain.ClubMember) -> bool:
        clubs = self._load()
        for c in clubs:
            if int(c.get("id") or 0) == int(club_id):
                members = c.setdefault("members", [])
                if any(int(m.get("user_id")) == int(member.user_id) for m in members):
                    return False
                members.append(member.to_dict())
                self._save(clubs)
                return True
        return False

    def set_member_status(self, club_id: int, user_id: int, status: str) -> bool:
        clubs = self._load()
        for c in clubs:
            if int(c.get("id") or 0) == int(club_id):
                for m in c.get("members", []):
                    if int(m.get("user_id")) == int(user_id):
                        m["status"] = status
                        self._save(clubs)
                        return True
        return False

    def is_active_member(self, club_id: int, user_id: int) -> bool:
        for c in self._load():
            if int(c.get("id") or 0) == int(club_id):
                return any(
                    int(m.get("user_id")) == int(user_id) and m.get("status") == "active"
                    for m in c.get("members", [])
                )
        return False
