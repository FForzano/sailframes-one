# XGSail — Sailing Analytics Platform

## Project Context for Claude Code

This repository is **XGSail**: the software application layer only —
backend API, frontend SPA, ingestion/processing workers, and
self-hosted deployment. It is **not** the hardware/firmware repository.
Firmware, PCB design (KiCad), and embedded-device internals live in the
separate upstream project (SailFrames Core) and are out of scope here.

XGSail is an open-source (Apache 2.0) fork of SailFrames: it keeps the
original's license and general purpose — sailing session analytics —
but the data model, API surface, and frontend have been substantially
redesigned rather than incrementally patched. See "Structural
differences from upstream" in `README.md` for specifics.

XGSail is hardware-agnostic by design: devices integrate through
a stable, documented ingestion contract (`docs/device-protocol.md`)
rather than through code that assumes a specific board. See
`README.md` for the full scope statement ("What XGSail Is" /
"Is Not").

---

## Project Overview

- **License:** Apache 2.0
- Self-hosted first: `docker compose up --build` brings up the entire
  stack locally (Postgres + MinIO + backend + frontend + workers), with
  the same code deploying to AWS (S3/Lambda) via env-gated config — no
  code forks between the two targets.
- **Status:** the users/auth/roles/clubs/groups/devices redesign (formerly
  tracked on `feature/introduce-users-login-and-roles`) has landed on
  `main` — schema, API, and frontend already reflect it. `docs/` now
  holds `device-protocol.md` (the ingestion contract, still the source of
  truth) and `estimation-pipeline.md` (how raw sensor/API data becomes
  legs/maneuvers/VMG/polar numbers); the original `er-project.md` /
  `api-project.md` / `frontend-project.md` design docs have been
  retired now that the redesign they specified is implemented.

---

## Code Style Guidelines

Applies across the whole repo (backend, frontend, workers) — not
project-specific:

- **Simple and readable over clever.** Optimize for the next person
  reading the code, not for fewest lines or cleverest trick.
- **Isolate responsibilities.** Each function/module does one thing.
  Router modules stay thin (HTTP concerns only); business logic lives in
  `services`/`repositories`; don't mix request parsing, DB access, and
  response shaping in one function just because they run back-to-back.
- **Reuse before writing.** Before adding a new helper, check if an
  existing function in the codebase (or a well-maintained library
  already in use — e.g. an existing repository method, a `services/`
  helper, a frontend hook) already does it. Prefer extending/
  parameterizing an existing function over writing a near-duplicate.
- **No duplicated logic.** If the same block of logic (even
  slightly-modified copy-paste) appears in two places, extract it into a
  shared function — favor small, composable, modular pieces over
  repeating inline logic. This matters especially for router modules
  (shared HTTP helpers belong in `routers/_common.py`, not copy-pasted
  per router) and for the frontend (shared chart/map/data-fetching logic
  belongs in a hook/util, not duplicated per page).

---

## Repository Structure

```
core/
├── CLAUDE.md              # This file
├── README.md               # Project scope: what XGSail is / isn't
├── docs/
│   ├── device-protocol.md   # Hardware-agnostic device integration protocol
│   └── estimation-pipeline.md # Position/wind/maneuver estimation pipeline
├── backend/                # FastAPI REST API (API-only, no static mount)
│   ├── main.py               # Composition root: CORS, RBAC startup seed, routers
│   ├── routers/               # One module per resource (see below)
│   ├── services/                # Business logic (course, geo, gpx, wind estimation,
│   │                               import processing, maneuver reconciliation)
│   ├── repositories/              # Data-access layer (base.py + sql/ implementation)
│   ├── auth/                        # passwords, tokens, permissions, RBAC seed
│   ├── db/                            # SQLAlchemy models + base, Alembic-migrated
│   ├── storage/                        # Object-store abstraction (S3/MinIO)
│   ├── schemas/                          # Pydantic request/response models
│   └── alembic/                            # DB migrations
├── frontend/                # Vite + TypeScript SPA (TanStack Query, react-router,
│   └── src/                   # leaflet, recharts, i18next)
│       # pages/ groups routes by area: diario/ (activities, sessions, races,
│       # regattas, import), gruppi/ (clubs, groups, devices), profilo/
│       # (account, boats, devices, password), admin/ (superadmin)
├── workers/                 # Heavy-processing workers — same handler runs on AWS
│   ├── process_upload/        # Lambda (container image): GPS/CSV/GPX → analysis
│   ├── train_maneuver/         # Maneuver-detector training/export tooling
│   └── video/                   # MP4 → HLS via ffmpeg, Lambda Runtime Interface Emulator
├── deploy/                  # Self-hosted stack: Dockerfile.backend, minio-init.sh
├── scripts/                 # One-off/maintenance scripts (migrations, backfills,
│                              wind-weight calibration, training-data export)
└── docker-compose.yml       # One-command local stack (postgres/minio/backend/
                               frontend/process_upload/video/train_maneuver)
```

### Backend routers (`backend/routers/`)

One module per resource, registered in `routers/__init__.py`
(`ALL_ROUTERS`): `auth`, `users`, `rbac`, `boats`, `clubs`, `groups`,
`devices`, `activities`, `sessions`, `polars`, `regattas`, `racedays`,
`races`, `device_api`, `imports`, `ingest`, `uploads`, `download`,
`wind`, `system`, `video`. Shared HTTP helpers live in
`routers/_common.py` — put anything reused across routers there, not
copy-pasted.

Principals differ per router: cookie-authenticated users (most
routers), `DeviceKey`-authenticated hardware (`device_api`), hook-token
system callers (`system` + the `ingest` webhook), and the token-signed
upload/download proxies (`uploads`, `download`). Devices integrate via
the claim + device-key flow in `docs/device-protocol.md` — there is no
device-specific upload path left in the router layer.

---

## Data Flow

```
[Device or manual import]
  → presigned upload URL (backend/storage) → PUT to S3/MinIO

[Object storage]
  ObjectCreated event → webhook (MinIO: /hooks/minio, or S3 notification)
  → backend invokes workers/process_upload (or workers/video for video
    files) over HTTP — same container image also runs as a Lambda in
    the AWS deployment, via the Lambda Runtime Interface Emulator
  → worker writes processed/normalized data back to storage + updates
    ingestion status in Postgres via the backend

[Frontend]
  SPA (frontend/) → REST API (backend/) → Postgres (metadata) +
  object storage (processed data, referenced by data_ref/raw_ref)
```

See `docs/estimation-pipeline.md` for how raw GPS/wind readings become
the legs/maneuvers/VMG/polar numbers shown in session analysis, and
`docs/device-protocol.md` before changing anything upload/ingestion-related.

---

## Self-Hosted Stack

```bash
cp .env.example .env   # edit secrets — never commit a real .env
docker compose up --build
```

Services (see `docker-compose.yml`): `postgres` (metadata), `minio`
(S3-compatible blob storage, console on :9001), `backend` (FastAPI,
:8000), `frontend` (nginx serving the SPA build + proxying `/api` →
backend, same-origin), plus the `process_upload`/`video`/`train_maneuver`
workers invoked by the backend on MinIO upload events. See
`deploy/README.md` for the full request-flow diagram and how the
self-hosted (MinIO) path differs from the AWS (S3/Lambda) path — same
code, env-gated.

---

## Weather Data Integration

- **NOAA NDBC buoys**, **METAR** stations, and **Cumulus** personal
  weather stations, fetched via `backend/services/wind_providers/` and
  exposed through `backend/routers/wind.py`.
- `wind_stations` / `wind_observations` (see `backend/db/models/wind.py`)
  cache this external data locally (avoids re-fetching on every render,
  preserves history past whatever window the upstream API retains).
  Station selection/aggregation and the estimation algorithms that turn
  raw observations into a usable wind signal are documented in
  `docs/estimation-pipeline.md`.

---

## Auth & RBAC

Two authorization layers:

1. **Scoped RBAC** (`roles`/`permissions`/`role_permissions`/`user_roles`,
   see `backend/db/models/rbac.py` + `backend/routers/rbac.py`) for
   institutional roles (`superadmin`, `club_admin`, `race_officer`)
   scoped via `user_roles.scope_club_id`.
2. **Per-resource ownership** (`user_boats.role`, `user_groups.role`) for
   personal/boat-scoped resources — no centralized permission check, the
   relationship itself grants access.

`backend/auth/` implements passwords, JWT tokens, and the RBAC seed run
at startup (`seed_superadmin`, `seed_device_types`, `seed_defaults` in
`main.py`).

---

*This file was realigned to reflect XGSail's actual scope (software
application only) — hardware/firmware/PCB content that previously
lived here belongs to the separate upstream SailFrames Core (hardware)
project and is no longer relevant to this repository.*
