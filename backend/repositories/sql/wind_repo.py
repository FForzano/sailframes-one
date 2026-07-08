"""SQL wind repository: ``wind_stations`` + ``wind_observations`` cache.

``upsert_observations`` relies on the unique (wind_station_id, observed_at)
constraint with ``ON CONFLICT DO NOTHING`` so the periodic fetch job is
idempotent by construction.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...db.models import WindObservationORM, WindStationORM

_STATION_FIELDS = ("provider", "external_station_id", "name", "station_type", "lat", "lng")
_OBS_FIELDS = ("observed_at", "twd_deg", "tws_kts", "gust_kts", "is_forecast")


class SqlWindRepo:
    def __init__(self, session_factory):
        self.Session = session_factory

    # --- stations ---

    def list(self, *, provider: Optional[str] = None) -> "list[WindStationORM]":
        with self.Session() as s:
            q = select(WindStationORM)
            if provider is not None:
                q = q.where(WindStationORM.provider == provider)
            return list(s.scalars(q).all())

    def get(self, station_id: uuid.UUID) -> Optional[WindStationORM]:
        with self.Session() as s:
            return s.get(WindStationORM, station_id)

    def get_by_provider_external(self, provider: str,
                                 external_station_id: str) -> Optional[WindStationORM]:
        with self.Session() as s:
            return s.scalars(
                select(WindStationORM).where(
                    WindStationORM.provider == provider,
                    WindStationORM.external_station_id == external_station_id,
                )
            ).first()

    def create(self, data: dict) -> WindStationORM:
        with self.Session() as s:
            orm = WindStationORM(**{k: data.get(k) for k in _STATION_FIELDS if k in data})
            s.add(orm)
            s.commit()
            new_id = orm.id
        return self.get(new_id)

    def update(self, station_id: uuid.UUID, changes: dict) -> Optional[WindStationORM]:
        with self.Session() as s:
            orm = s.get(WindStationORM, station_id)
            if orm is None:
                return None
            for k, v in changes.items():
                if k in _STATION_FIELDS:
                    setattr(orm, k, v)
            s.commit()
        return self.get(station_id)

    def delete(self, station_id: uuid.UUID) -> bool:
        with self.Session() as s:
            orm = s.get(WindStationORM, station_id)
            if orm is None:
                return False
            s.delete(orm)
            s.commit()
            return True

    # --- observations ---

    def upsert_observations(self, station_id: uuid.UUID, rows: "list[dict]") -> int:
        """Insert observations, silently skipping (station, observed_at)
        duplicates. Returns the number actually inserted."""
        if not rows:
            return 0
        values = [
            {"wind_station_id": station_id,
             **{k: r.get(k, False) if k == "is_forecast" else r.get(k) for k in _OBS_FIELDS}}
            for r in rows
        ]
        with self.Session() as s:
            stmt = (
                pg_insert(WindObservationORM)
                .values(values)
                .on_conflict_do_nothing(index_elements=["wind_station_id", "observed_at"])
                .returning(WindObservationORM.id)  # rowcount is -1 for ON CONFLICT inserts
            )
            inserted = len(s.execute(stmt).fetchall())
            s.commit()
            return inserted

    def reconcile_observations(self, station_id: uuid.UUID, rows: "list[dict]") -> int:
        """Overwrite existing (station, observed_at) rows with settled values
        — unlike ``upsert_observations`` (which skips duplicates so the
        periodic fetch stays cheap), this is for the reconciliation job
        replacing provisional forecast readings with the archive's reanalysis
        once it's had time to catch up. Returns the number of rows written."""
        if not rows:
            return 0
        values = [
            {"wind_station_id": station_id,
             **{k: r.get(k, False) if k == "is_forecast" else r.get(k) for k in _OBS_FIELDS}}
            for r in rows
        ]
        with self.Session() as s:
            stmt = pg_insert(WindObservationORM).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["wind_station_id", "observed_at"],
                set_={
                    "twd_deg": stmt.excluded.twd_deg,
                    "tws_kts": stmt.excluded.tws_kts,
                    "gust_kts": stmt.excluded.gust_kts,
                    "is_forecast": stmt.excluded.is_forecast,
                    "fetched_at": func.now(),
                },
            )
            s.execute(stmt)
            s.commit()
            return len(values)

    def stations_with_stale_forecasts(self, cutoff: datetime) -> "list[uuid.UUID]":
        """Distinct station ids that still have forecast-sourced rows older
        than ``cutoff`` — candidates for the reconciliation job."""
        with self.Session() as s:
            q = (
                select(WindObservationORM.wind_station_id)
                .where(WindObservationORM.is_forecast.is_(True),
                       WindObservationORM.observed_at < cutoff)
                .distinct()
            )
            return list(s.scalars(q).all())

    def stale_forecast_range(self, station_id: uuid.UUID,
                             cutoff: datetime) -> "Optional[tuple[datetime, datetime]]":
        """``(min, max) observed_at`` of a station's not-yet-reconciled
        forecast rows older than ``cutoff``, or ``None`` if there are none —
        lets the reconciliation job fetch one archive range per station
        instead of one call per stale hour."""
        with self.Session() as s:
            lo, hi = s.execute(
                select(func.min(WindObservationORM.observed_at),
                      func.max(WindObservationORM.observed_at))
                .where(WindObservationORM.wind_station_id == station_id,
                      WindObservationORM.is_forecast.is_(True),
                      WindObservationORM.observed_at < cutoff)
            ).one()
            return None if lo is None else (lo, hi)

    def list_observations(self, station_id: uuid.UUID, *,
                          start: Optional[datetime] = None,
                          end: Optional[datetime] = None,
                          limit: int = 500, offset: int = 0) -> "list[WindObservationORM]":
        """Paginated, newest-first (page 0 = most recent). The cache grows
        without bound (idempotent upsert on every scheduler tick) — callers
        MUST page through it rather than fetch it whole; see the default
        72h window in ``routers/wind.py`` when start/end are omitted."""
        with self.Session() as s:
            q = select(WindObservationORM).where(
                WindObservationORM.wind_station_id == station_id
            )
            if start is not None:
                q = q.where(WindObservationORM.observed_at >= start)
            if end is not None:
                q = q.where(WindObservationORM.observed_at <= end)
            q = q.order_by(WindObservationORM.observed_at.desc()).limit(limit).offset(offset)
            return list(s.scalars(q).all())

    def find_nearest(self, lat: float, lng: float, *,
                     providers: "Optional[list[str]]" = None,
                     max_km: float = 50) -> Optional[WindStationORM]:
        """Closest station within ``max_km``, optionally restricted to
        ``providers`` (haversine, computed in Python — station counts are
        small, no need for PostGIS). Provider quality tiers (real sensors vs.
        forecast grid) are the caller's job — see
        ``services/wind_lookup.find_or_create_station``."""
        from ...services.geo import haversine_m

        with self.Session() as s:
            q = select(WindStationORM).where(
                WindStationORM.lat.is_not(None), WindStationORM.lng.is_not(None)
            )
            if providers is not None:
                q = q.where(WindStationORM.provider.in_(providers))
            stations = list(s.scalars(q).all())
        best, best_km = None, max_km
        for st in stations:
            km = haversine_m(lat, lng, st.lat, st.lng) / 1000
            if km <= best_km:
                best, best_km = st, km
        return best
