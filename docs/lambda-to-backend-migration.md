# Lambda to Backend Migration Status

This file tracks the migration from AWS Lambda HTTP handlers to local FastAPI routers.

## Directory Moves Applied

- Renamed `web/api/` -> `backend/`.
- Renamed `web/frontend/` -> `frontend/`.
- Created `workers/` and moved non-API modules from `lambda/`:
  - `workers/process_upload/`
  - `workers/ppk_process/`
  - `workers/transcode_video/`
  - `workers/transcode_complete/`
  - `workers/link_videos/`
  - `workers/cors_download/`

## API Coverage: lambda/api_* vs backend/routers

### Fully covered in backend (safe candidates for removal after runtime validation)

- `lambda/api_e1` -> `backend/routers/e1.py`
- `lambda/api_sessions` -> `backend/routers/sessions.py`
- `lambda/api_data` -> `backend/routers/data.py`
- `lambda/api_analysis` -> `backend/routers/analysis.py`
- `lambda/api_buoys` -> `backend/routers/buoys.py`

### Mostly covered, with partial parity work completed

- `lambda/api_race` -> `backend/routers/races.py`, `backend/routers/regattas.py`,
  `backend/routers/racedays.py`, `backend/routers/boats.py`, `backend/routers/leaderboard.py`

Already integrated during migration:
- race data padding query params (`pad_start`, `pad_end`)
- `GET /api/races/{race_id}/gpx-status`
- `GET /api/races/{race_id}/ais`

Remaining parity gaps from legacy `api_race` to evaluate:
- `POST /api/races/{race_id}/boats-by-id/{boat_id}/gpx`
- `POST /api/races/{race_id}/boats-by-id/{boat_id}/vkx`

### Not yet migrated to backend routers

- `lambda/api_chat`
- `lambda/api_coach`
- `lambda/api_screenshot`
- `lambda/api_video` (legacy handler behavior differs from current `backend/routers/video.py`)

## Workers / Shared Runtime Notes

- Docker now runs `backend.main:app`.
- `workers/process_upload/handler.py` is reused by `POST /hooks/minio` via `PYTHONPATH`.

## Infrastructure Status

`infrastructure/` is marked as **remove only after migration completion**.

Removal gate:
1. Remaining API parity gaps closed.
2. Lambda-only features (chat/coach/screenshot/video transcode flow) migrated or intentionally dropped.
3. Deploy and rollback paths validated without AWS Lambda.

## processing/, export/, services/ Evaluation

- `processing/`: keep; core analytics logic used by backend and workers.
- `export/`: keep for now; contains report/video export capabilities not replaced yet.
- `services/`: evaluate case-by-case; keep until each service is either integrated into backend/workers or confirmed obsolete.