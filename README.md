# SailFrames One

Open sailing analytics platform for race analysis, session replay, and fleet performance — self-hostable, hardware-agnostic, and built for extensibility.

SailFrames One is a software-first evolution of the original SailFrames project. It focuses on the application layer: user management, authentication, roles, data ingestion, storage, analytics, and web-based workflows for sailors, coaches, and teams.

## What SailFrames One Is

SailFrames One is a platform for collecting, storing, and analyzing sailing session data.

It is designed to support:

- Self-hosted deployments
- User authentication and role-based access
- Database-backed storage
- Session and race analysis workflows
- Replay and coaching-oriented review tools
- Hardware-agnostic ingestion through a defined protocol

The goal is to provide an open platform for sailing analytics that can work with dedicated devices, custom integrations, or external data sources, without tying the application to one specific hardware stack.

## What SailFrames One Is Not

SailFrames One is **not** the hardware, firmware, or embedded edge stack from the original SailFrames repository.

Those components may integrate with SailFrames One, but this repository is focused on the software platform and its data contract.

## Project Scope

This repository is intended to contain:

- Backend API
- Frontend application
- Database models and migrations
- Authentication and authorization
- Storage and ingestion services
- Analytics and replay workflows
- Protocol and integration documentation
- Self-hosted deployment configuration

## Architecture Direction

SailFrames One follows a software-platform approach:

1. Devices or external tools produce sailing data.
2. Data is uploaded using a stable ingestion contract.
3. The backend validates, stores, and processes session data.
4. The web application exposes analysis, replay, and management features.

This separation allows the platform to evolve independently from any one hardware implementation.

## Repository Status

SailFrames One is currently under active development.

The current focus includes:

- Introducing users, login, and roles
- Moving toward database-backed persistence
- Replacing legacy cloud-specific assumptions
- Defining a cleaner ingestion model for future device compatibility
- Restructuring backend and frontend for long-term maintainability

## Planned Capabilities

- User accounts and organization/team workflows
- Roles and permissions
- Session import and ingestion APIs
- Boat, crew, and event management
- Race/session replay
- Performance metrics and comparative analysis
- Self-hosted deployment
- Support for multiple device or data-provider integrations

## Relationship to SailFrames Core

SailFrames One is derived from the broader SailFrames effort, but it intentionally narrows the scope to the software application layer.

Where the original project includes hardware, firmware, edge devices, and AWS-oriented infrastructure, SailFrames One aims to become a cleaner, self-hostable analytics platform with a stable integration surface for present and future devices.

## Principles

- **Open** — users can inspect, run, and extend the platform
- **Self-hostable** — no mandatory vendor lock-in
- **Hardware-agnostic** — devices integrate through protocols, not tight coupling
- **Maintainable** — clear boundaries between frontend, backend, storage, and processing
- **Extensible** — new integrations should not require rewriting the core platform

## Quick start (self-host)

Everything runs as containers. From the repo root:

```bash
docker compose up --build
```

Then open **http://localhost:8080**. That's the whole stack:

| Service | Port | What it is |
|---|---|---|
| `frontend` | 8080 | The SPA (nginx). Serves the app and proxies `/api` → backend, so it's all one origin. |
| `backend` | 8000 | The REST API (FastAPI). Also reachable directly for debugging. |
| `postgres` | 5432 | Metadata (users, boats, sessions, races, RBAC). |
| `minio` | 9000 / 9001 | S3-compatible blob storage (sensor data, video, manifests) + console. |
| `process_upload`, `video` | — | Heavy-processing workers (see below). |

No `.env` is required — every value has a dev default. Copy `.env.example` to
`.env` to override secrets for a real deployment.

## Architecture

- **One API.** The FastAPI `backend/` is the only API surface. Metadata lives in
  Postgres; large files (CSV sensor data, video, JSON results) live in S3/MinIO.
- **Auth.** Native email/password (Argon2id) → JWT access cookie + rotating
  refresh token, with double-submit CSRF and per-club RBAC.
- **Workers as microservices.** `workers/process_upload` (GPS tracks + analysis)
  and `workers/video` (MP4 → HLS via ffmpeg) are built on the AWS Lambda base
  image. The **same image** runs on AWS Lambda and locally: in compose it runs
  via the Lambda Runtime Interface Emulator that ships in the base image, and the
  backend invokes it over HTTP on a MinIO upload event (`/hooks/minio`). On AWS
  the identical image sits behind an S3 → Lambda trigger. No code changes to move
  between the two.

Repo layout: `backend/` · `frontend/` · `workers/{process_upload,video}/` ·
`deploy/` (Dockerfile + MinIO init) · `scripts/` (migrations, image build) ·
`docs/`.

## License

Apache 2.0, consistent with the original upstream project unless stated otherwise.