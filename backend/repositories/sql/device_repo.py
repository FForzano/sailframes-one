"""SQL device repository (+ attribution windows). Reads return ``DeviceORM``;
``add_assignment`` rejects overlapping windows (409 at the router). Attribution
order: covering window at ``at`` -> ``default_boat_id`` -> None."""

from typing import Optional

from sqlalchemy import select, update

from ...db.models import DeviceORM, DeviceAssignmentORM


def _windows_overlap(a_from, a_to, b_from, b_to) -> bool:
    """True if half-open [a_from,a_to) and [b_from,b_to) intersect. ISO-8601
    strings compare lexicographically; None bounds are open on their side."""
    a_before_b_end = a_from is None or b_to is None or a_from < b_to
    b_before_a_end = b_from is None or a_to is None or b_from < a_to
    return a_before_b_end and b_before_a_end


def _covers(valid_from, valid_to, at) -> bool:
    if valid_from is not None and at < valid_from:
        return False
    if valid_to is not None and at >= valid_to:
        return False
    return True


class SqlDeviceRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    def list(self) -> list[DeviceORM]:
        with self.Session() as s:
            return list(s.scalars(select(DeviceORM)).all())

    def get(self, device_id: str) -> Optional[DeviceORM]:
        with self.Session() as s:
            return s.get(DeviceORM, device_id)

    def register(self, data: dict) -> DeviceORM:
        with self.Session() as s:
            orm = s.get(DeviceORM, data["device_id"])
            if orm is None:
                orm = DeviceORM(device_id=data["device_id"])
                s.add(orm)
            orm.name = data.get("name")
            orm.device_type = data.get("device_type") or "sailframes_e"
            orm.default_boat_id = data.get("default_boat_id")
            orm.owner_type = data.get("owner_type") or "user"
            orm.registered_by = data.get("registered_by")
            orm.owned_by_club_id = data.get("owned_by_club_id")
            orm.status = data.get("status") or "active"
            orm.created_at = data.get("created_at")
            orm.last_seen_at = data.get("last_seen_at")
            s.commit()
        return self.get(data["device_id"])

    def add_assignment(self, *, device_id: str, boat_id: str, valid_from=None, valid_to=None,
                       regatta_id=None, race_id=None, created_by=None,
                       created_at=None) -> DeviceAssignmentORM:
        with self.Session() as s:
            if s.get(DeviceORM, device_id) is None:
                raise ValueError(f"Unknown device: {device_id}")
            existing = s.scalars(
                select(DeviceAssignmentORM).where(DeviceAssignmentORM.device_id == device_id)
            ).all()
            for e in existing:
                if _windows_overlap(valid_from, valid_to, e.valid_from, e.valid_to):
                    raise ValueError("Assignment window overlaps an existing one")
            orm = DeviceAssignmentORM(
                device_id=device_id, boat_id=boat_id, regatta_id=regatta_id, race_id=race_id,
                valid_from=valid_from, valid_to=valid_to, created_by=created_by, created_at=created_at,
            )
            s.add(orm)
            s.commit()
            s.refresh(orm)
            s.expunge(orm)
            return orm

    def list_assignments(self, device_id: str) -> "list[DeviceAssignmentORM]":
        with self.Session() as s:
            return list(s.scalars(
                select(DeviceAssignmentORM).where(DeviceAssignmentORM.device_id == device_id)
            ).all())

    def resolve_boat(self, device_id: str, at_iso: str) -> Optional[str]:
        dev = self.get(device_id)
        if dev is None:
            return None
        for a in dev.assignments:
            if _covers(a.valid_from, a.valid_to, at_iso):
                return a.boat_id
        return dev.default_boat_id

    def touch_last_seen(self, device_id: str, at_iso: str) -> bool:
        with self.Session() as s:
            res = s.execute(
                update(DeviceORM).where(DeviceORM.device_id == device_id).values(last_seen_at=at_iso)
            )
            s.commit()
            return res.rowcount > 0
