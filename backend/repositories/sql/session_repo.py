"""SQL session repository.

The DB is the source of truth for session metadata (owner, crew, visibility,
boat_id). Reads return ``SessionORM`` rows; a historical manifest not yet imported
is surfaced as a transient ``SessionORM`` (``get``) and promoted to a real row the
first time it is attributed/edited. Writes are the ingest boat-attribution
(``attribute_boat``) and the crew/privacy edit (``edit``).
"""

from typing import Optional

from sqlalchemy import select

from ...db.models import SessionORM, SessionCrewORM
from ._blob_sessions import get_blob_session, list_blob_sessions


class SqlSessionRepo:
    def __init__(self, session_factory, blob, data_prefix: str):
        self.Session = session_factory
        self._blob = blob
        self._data_prefix = data_prefix

    @staticmethod
    def _by_key(s, device_id: str, date: str) -> Optional[SessionORM]:
        return s.scalars(
            select(SessionORM).where(SessionORM.device_id == device_id, SessionORM.date == date)
        ).first()

    def list(self) -> list[SessionORM]:
        with self.Session() as s:
            return list(s.scalars(select(SessionORM)).all())

    def get_by_id(self, session_id: int) -> Optional[SessionORM]:
        with self.Session() as s:
            return s.get(SessionORM, session_id)

    def create_manual(self, *, boat_id: str, date: str, name: Optional[str],
                       crew: list, owner_user_id: int) -> SessionORM:
        """Register a device-less outing (``source="manual"``). Starts life with
        no data/analysis — ``processing_status="pending"`` until a GPX track is
        uploaded and processed (see ``services/gpx_processing.py``)."""
        with self.Session() as s:
            orm = SessionORM(
                device_id=None,
                date=date,
                boat=boat_id,
                boat_id=boat_id,
                name=name,
                source="manual",
                processing_status="pending",
                visibility="private",
                owner_user_id=owner_user_id,
                sensors=[],
            )
            orm.crew = [
                SessionCrewORM(user_id=c.get("user_id"), guest_name=c.get("guest_name"),
                               boat_role=c.get("boat_role"))
                for c in crew
            ]
            s.add(orm)
            s.commit()
            s.refresh(orm)
            return orm

    def set_processing_status(self, session_id: int, status: str, error: Optional[str] = None) -> None:
        with self.Session() as s:
            orm = s.get(SessionORM, session_id)
            if orm is None:
                return
            orm.processing_status = status
            orm.processing_error = error
            s.commit()

    def apply_manual_gpx_result(self, session_id: int, *, start_time: Optional[str],
                                 end_time: Optional[str], duration_sec: Optional[int],
                                 sensors: dict, has_analysis: bool,
                                 status: str, error: Optional[str] = None) -> None:
        """Persist the outcome of ``services/gpx_processing.py`` onto the
        session row: the manifest-derived summary fields (mirroring what the
        CSV ingest pipeline keeps in sync for device sessions) plus the final
        ``processing_status``."""
        with self.Session() as s:
            orm = s.get(SessionORM, session_id)
            if orm is None:
                return
            orm.start_time = start_time
            orm.end_time = end_time
            orm.duration_sec = duration_sec
            orm.sensors = sensors
            orm.has_analysis = has_analysis
            orm.processing_status = status
            orm.processing_error = error
            s.commit()

    def get(self, device_id: str, date: str) -> Optional[SessionORM]:
        with self.Session() as s:
            orm = self._by_key(s, device_id, date)
            if orm is not None:
                return orm
        # Historical manifest not yet imported: return it as a transient row.
        return get_blob_session(self._blob, self._data_prefix, device_id, date)

    def attribute_boat(self, device_id: str, date: str, boat_id: str) -> None:
        """Ingest hook: snapshot the device->boat attribution onto the session.
        Idempotent; never overwrites a user-claimed session. Imports the blob
        manifest as a new row if the session isn't in the table yet."""
        with self.Session() as s:
            orm = self._by_key(s, device_id, date)
            if orm is not None:
                if orm.owner_user_id is None and boat_id and orm.boat_id != boat_id:
                    orm.boat_id = boat_id
                    if not orm.boat:
                        orm.boat = boat_id
                    s.commit()
                return
            transient = get_blob_session(self._blob, self._data_prefix, device_id, date)
            if transient is None:
                return
            transient.boat_id = boat_id
            if not transient.boat:
                transient.boat = boat_id
            s.add(transient)
            s.commit()

    def edit(self, device_id: str, date: str, *, crew: list, boat_id=None, visibility=None,
             club_id=None, group_id=None, claim_owner_id=None) -> Optional[SessionORM]:
        """Crew/privacy edit. Replaces the crew wholesale; sets the provided
        fields; claims the session for ``claim_owner_id`` if unowned. Imports a
        blob-only session first so the edit has a row to write to."""
        with self.Session() as s:
            orm = self._by_key(s, device_id, date)
            if orm is None:
                orm = get_blob_session(self._blob, self._data_prefix, device_id, date)
                if orm is None:
                    return None
                s.add(orm)
                s.flush()
            orm.crew = [
                SessionCrewORM(user_id=c.get("user_id"), guest_name=c.get("guest_name"),
                               boat_role=c.get("boat_role"))
                for c in crew
            ]
            if boat_id is not None:
                orm.boat_id = boat_id
            if visibility is not None:
                orm.visibility = visibility
            if club_id is not None:
                orm.club_id = club_id
            if group_id is not None:
                orm.group_id = group_id
            if orm.owner_user_id is None and claim_owner_id is not None:
                orm.owner_user_id = claim_owner_id
            s.commit()
        return self.get(device_id, date)

    def bootstrap_from_blob(self) -> int:
        """One-shot import of blob manifests into the table (migration helper).
        Only inserts rows that do not exist yet."""
        imported = 0
        with self.Session() as s:
            for orm in list_blob_sessions(self._blob, self._data_prefix):
                if self._by_key(s, orm.device_id, orm.date) is None:
                    s.add(orm)
                    imported += 1
            s.commit()
        return imported
