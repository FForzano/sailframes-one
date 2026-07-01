"""FastAPI backend for SailFrames analysis dashboard.

Composition root only: builds the app, wires middleware + the RBAC startup
seed, includes every router from ``backend/routers`` (one module per resource),
and mounts the static frontend last. All endpoint logic lives in the router
modules; shared HTTP helpers live in ``routers/_common.py``. Designed to run
locally or behind API Gateway in AWS.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import ALL_ROUTERS

app = FastAPI(
    title="SailFrames Analysis API",
    version="1.0.0",
    description="Sailboat racing analysis and replay dashboard",
)

# Credentialed cookie auth (sf_access/sf_csrf) is incompatible with a wildcard
# origin, so CORS is an explicit allow-list. In production the SPA is served
# same-origin (no CORS exercised); this list matters for the Vite dev server
# and any split-origin deploy. Override with SAILFRAMES_CORS_ORIGINS (CSV).
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "SAILFRAMES_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _seed():
    """Seed the bootstrap superadmin + the physical E1–E6 device registry (both
    backends) and, on Postgres, the default RBAC roles/permissions."""
    from .auth import seed_superadmin, seed_devices
    from .repositories import get_repos

    repos = get_repos()
    seed_superadmin(repos)
    seed_devices(repos)
    if os.environ.get("SAILFRAMES_METADATA_BACKEND", "object").lower() == "postgres":
        from .auth import seed_defaults
        from .db import get_sessionmaker
        seed_defaults(get_sessionmaker())


# Include every resource router (E1 fleet, sessions, data, analysis, boats,
# leaderboard, video, buoys, races/regattas/racedays, fleet status, ingest).
for _router in ALL_ROUTERS:
    app.include_router(_router)


# --- Static files (frontend SPA) ---
# Mounted LAST so the catch-all "/" does not shadow the API routes above.
# Serves the built Vite SPA (``frontend/dist``). Unknown non-file paths fall
# back to ``index.html`` so client-side deep links (e.g. ``/races/123``) resolve
# on reload instead of 404-ing.
class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        from starlette.exceptions import HTTPException as StarletteHTTPException

        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if (dist_dir / "index.html").exists():
    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="frontend")
