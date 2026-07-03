"""HTTP controller layer for SailFrames.

One module per resource, each exposing an ``APIRouter`` as ``router``. ``main``
imports ``ALL_ROUTERS`` and includes them on the app; shared HTTP helpers live
in ``_common``.

er-project phase: routers built on the pre-redesign schema are temporarily
disabled (imports AND registrations commented out — several would fail at
import against the new models/repos). They get rebuilt against
docs/api-project.md in the next phase. Enabled: auth (updated) + the
blob/external-only modules that never touch the DB.
"""

from . import (
    auth,
    e1,
    fleet,
    download,
    video,
    leaderboard,
    buoys,
    # --- disabled until the api-project phase (old-schema dependencies) ---
    # uploads,
    # sessions,
    # data,
    # analysis,
    # ingest,
    # boats,
    # clubs,
    # groups,
    # devices,
    # regattas,
    # racedays,
    # races,
)

ALL_ROUTERS = [
    # User system (auth only, for now)
    auth.router,
    # Fleet raw data + downloads (legacy E1 path + blob-only modules)
    e1.router,
    fleet.router,
    download.router,
    video.router,
    leaderboard.router,
    buoys.router,
    # --- disabled until the api-project phase ---
    # uploads.router,
    # sessions.router,
    # data.router,
    # analysis.router,
    # ingest.router,
    # boats.router,
    # clubs.router,
    # groups.router,
    # devices.router,
    # regattas.router,
    # racedays.router,
    # races.router,
]

__all__ = ["ALL_ROUTERS"]
