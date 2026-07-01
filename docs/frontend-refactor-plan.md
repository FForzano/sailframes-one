# Frontend rewrite — Vite + React 18 + TypeScript (big-bang)

## Status

| Milestone | State | Notes |
|---|---|---|
| **M0 — Scaffold + auth + nav shell** | ✅ **done** (2026-07-01) | Vite+TS app at `frontend/`, providers, `api.ts`+CSRF+refresh, i18n (it/en), responsive MainContent/Navbar/Sidebar/ActionBar/Footer, route table, Login/Register, `RequireAuth`+guards, capability-aware Dashboard. Backend `GET /api/auth/capabilities` + CORS allow-list. `npm run build` (tsc + vite) green; dev server boots. |
| M1 — Public browse | ⬜ pending | |
| M2 — Personal area CRUD | ⬜ pending | |
| M3 — Admin + events | ⬜ pending | |
| M4 — Race replay dashboard | ⬜ pending | largest slice |
| M5 — Coach fold-in | ⬜ pending | |
| M6 — Deploy cutover | ⬜ pending | repoint static mount, delete `frontend/old/` |

### Directory layout (repo reorganized 2026-07-01)

The repo was flattened: what used to live under `web/` is now split.

- **`backend/`** — FastAPI app (was `web/api/`). Run as `backend.main:app`.
- **`frontend/`** — the **new** Vite+React+TS SPA (this is where we work; was
  planned as `web/app/`). App source in `frontend/src/`, build to `frontend/dist/`.
- **`frontend/old/`** — the **legacy** static site being refactored away (was
  `web/` top level): `*.html`, `assets/`, `coach/`, `config.js`, and the
  deprecated `frontend/` React stub (now `frontend/old/frontend/`). Deleted at M6.

Path references below predate the move; read `web/app/`→`frontend/`,
`web/api/`→`backend/`, and `web/<legacy>`→`frontend/old/<legacy>`.

## Context

The SailFrames web frontend is ~11 static HTML pages of vanilla JS with **no build step**
(the race replay dashboard alone, `web/assets/js/race-app.js`, is **11,383 lines** of Leaflet +
Chart.js + playback + OCS/leaderboard/wind/polar + discussion). Auth is fragmented across three
unrelated mechanisms (Cloudflare Access for admin, Google OAuth for the coach app, guest
localStorage for comments). Meanwhile the backend just grew a full user system across Phases 1–5
(native login, clubs, groups, devices, boat ownership, session privacy/crew) that the frontend
**does not surface at all**. A deprecated Vite+React stub sits unused at `web/frontend/`.

Goal: replace the whole frontend with a well-structured **Vite + React 18 + TypeScript** SPA whose
**codebase structure** mirrors the reference repo at
`/Users/federico/Documents/FPC-DEV/formandopercorsi-frontend` (NOT its visual style), align it to
the new backend features, and give it a **single unified personal area** whose navigation and
actions are filtered by the user's capabilities. Responsive: **Navbar on desktop, bottom ActionBar
on mobile**. Structure it so a future native app can reuse the API/types/auth layer.

Decisions (confirmed with user): **big-bang** (end state = full React, no legacy HTML) · **TypeScript** ·
**single app with clean seams** (extract a shared package/monorepo only when native work starts) ·
**enrich the backend** so the frontend is capability-aware.

## Approach

New app at **`web/app/`** (fresh Vite+React+TS), replacing the deprecated `web/frontend/` and folding
`web/coach/` in as a route area. **Cookie auth, not localStorage-Bearer**: the backend already sets
httpOnly `sf_access`/`sf_refresh` + JS-readable `sf_csrf`, so the API client uses
`credentials:'include'`, attaches `X-SF-CSRF` (read from the cookie) on every mutation, and does a
single refresh-on-401 retry. A thin **fetch wrapper** (~120 lines) beats axios here because there is
no token to inject — this also keeps `types/` framework-free for later native reuse.

Server stays the source of truth (visibility filter + `require_permission`); the capabilities payload
only decides what UI to *show*, never what's *allowed*.

### One backend change: `GET /api/auth/capabilities`
`/api/auth/me` stays a cheap identity check. Add a cookie-authenticated capabilities endpoint returning
roles + effective permissions (global vs per-club, mirroring `_user_has_permission`) + memberships:

```jsonc
{ "user": { "id":12, "email":"…", "is_superadmin":false },
  "roles": [ {"role":"club_admin","scope_club_id":3} ],
  "permissions": { "global":["session.delete"],
                   "byClub": { "3":["regatta.manage","raceday.manage","race.create","race.edit","race.delete","boat.edit","session.delete"] } },
  "memberships": { "clubsOwned":[3], "clubsMember":[3,7], "groups":[11], "boatsOwner":[21], "boatsSkipper":[21,25] } }
```
Files: `web/api/routers/auth.py` (endpoint), `web/api/auth/permissions.py`
(`effective_capabilities(user)` — walk `user.roles`, collapse `RolePermissionORM`, gather memberships
from repos), `web/api/schemas/auth.py` (DTOs). Frontend `can(perm, clubId?) =
is_superadmin || permissions.global.includes(perm) || permissions.byClub[clubId]?.includes(perm)`.

Also tighten `web/api/main.py` CORS from `allow_origins=["*"]` (incompatible with credentialed cookies)
to explicit dev (`http://localhost:5173`) + prod origins with `allow_credentials=True`.

### `web/app/src/` structure (mirrors the reference, adapted)
```
contexts/   AuthContext (user+caps+status, login/register/logout/refreshMe), Loading, Error, Toast
hooks/      useAuth, useCapabilities (can()/ownsClub()/isBoatOwner()…), useScreenWidth,
            useResource (fetch-state), usePolling, useTimeController
utils/      api.ts (fetch wrapper: credentials, X-SF-CSRF, single-flight refresh-on-401),
            csrf.ts, IsAuth.tsx (withAuth HOC), guards.ts (requireAuth/requirePerm/requireBoatOwner…),
            format.ts, geo.ts (VMG/bearing ported from race-app.js)
services/   one typed file per resource: auth, clubs, groups, devices, boats, sessions, races,
            regattas, racedays, leaderboard, fleet, analysis, data, buoys, video
types/      auth, capabilities, club, group, device, boat, session, race, regatta, raceday,
            leaderboard, fleet, analysis, buoy, video  (framework-free → future shared package)
i18n/       i18next init + locales/{it,en}.json
data/       navConfig.ts (typed, capability-driven; replaces reference's sidebarLinks.json)
stores/     timeController.ts (port of assets/js/utils/time-sync.js → subscribable store)
components/ layout/{MainContent,Navbar,Sidebar,ActionBar,Footer,AppShell},
            ui/{Card,InputField,Select,Modal,Drawer,Avatar,Button,Spinner,Toast,Table,Tabs,ConfirmDialog,EmptyState,Badge},
            auth/ clubs/ groups/ boats/ devices/ sessions/ regattas/ fleet/ coach/,
            race/{RaceDashboard,MapView,TrackLayer,MarkerLayer,WindOverlay,PolarOverlay,LaylineLayer,
                  ChartPanel,Timeline,PlaybackControls,Leaderboard,BoatDrawer,LegsModal,ManeuversModal,
                  DiscussionThread,VideoPlayer}
pages/      Home, Login, Register, NotFound,
            public/{RacesBrowser,RaceView,SessionView,FleetStatus,Bom,Battery},
            app/{Dashboard,MySessions,Clubs,ClubDetail,Groups,GroupDetail,Boats,BoatDetail,
                 Devices,DeviceDetail,Events,Admin,Coach,Profile}
```

`components/layout/MainContent.tsx` is the orchestrator (reference's pattern): renders Navbar +
Sidebar (desktop, logged-in) + ActionBar (mobile/tablet bottom tabs, logged-in) + Footer conditionally
by route and `useScreenWidth`. Route protection via `withAuth(Component, guard?)`.

### Unified personal area (`/app/*`) — capability → nav/actions
Single shell; `navConfig` entries carry `visible:(caps)=>boolean`; every mutation button is gated
independently. Summary: My Sessions (edit crew/visibility for owner/crew; **delete** only with
`session.delete`) · Groups (create any; manage if owner) · Clubs (create/join any; **invite** only for
`clubsOwned`) · Boats (**edit** if `boatsOwner/boatsSkipper` or `boat.edit`) · Devices (visible with a
boat or owned club; **register private** if boat owner/skipper, **club device + assignments** if club
manager) · Events (visible/gated per `regatta.manage`/`raceday.manage`/`race.*`) · Admin (cleanup +
`user.manage`, superadmin/admin) · Coach (folded coach app) · Profile. Public/anon area (always in
Navbar): Home, Races browser, public Race dashboard, public Session, Fleet, BOM, Battery.

### Serving
- **Dev:** `vite dev` on :5173 proxying `/api` → FastAPI :8000; run backend with
  `SAILFRAMES_COOKIE_SECURE=0` so cookies set over http. Calls stay relative (`/api/...`) → first-party
  cookies; `sf_refresh` path `/api/auth` preserved through the proxy.
- **Prod:** `vite build` → `frontend/dist`. Repoint `backend/main.py` static mount (currently
  `web_dir = parent.parent / "web"`, ~L71-73 — that dir no longer exists post-move, so the mount is
  silently skipped today) to `frontend/dist`. For the S3/CloudFront path, add a CloudFront `/api/*`
  behavior (no-cache, forward `Cookie` + `X-SF-CSRF`) and SPA 403/404→`/index.html` fallback.
- **`infrastructure/deploy.sh`:** `build_frontend` dir `frontend`→`app`; `dist_dir` →`web/app/dist`;
  remove the legacy `web/*.html` + `web/assets/` sync block and the `config.js` runtime shim (replace
  with build-time `VITE_API_BASE=/api`); invalidate `/*`.

### Race dashboard decomposition (the heavy milestone)
Port `assets/js/utils/time-sync.js` first → `stores/timeController.ts` (keep the `EventTarget` pub/sub;
expose via `useSyncExternalStore`) so map/charts/timeline stay in lockstep with **no rewrite of playback
math**. Keep the large sensor arrays in refs/the store (not React state) — only cursor position +
selected-boat id live in React state, to avoid re-render storms. Vanilla→React map: `map-view.js`→
`MapView`+layers (imperative Leaflet in a ref, not react-leaflet); `chart-panel.js`→`ChartPanel`
(`chart.update('none')` on cursor); `timeline.js`→`Timeline`+`PlaybackControls`; leaderboard/VMG/laylines→
`Leaderboard`+`utils/geo.ts`; `race-chat.js`→`DiscussionThread`; `video-player.js`→`VideoPlayer` (hls.js
ref); `boat-classes.js`→`utils/format.ts`+`types/boat.ts`.

## Milestones (each shippable behind a subpath until M6 cutover)
- **M0 — Scaffold + auth + nav shell.** `web/app/` Vite+TS, providers, `api.ts`+CSRF+refresh, i18n,
  MainContent+Navbar/Sidebar/ActionBar responsive, route table, Login/Register, `withAuth`,
  `useCapabilities`. Backend: `GET /api/auth/capabilities` + CORS tighten.
- **M1 — Public browse.** Home, RacesBrowser, FleetStatus, Bom, Battery, read-only SessionView.
- **M2 — Personal area CRUD.** Dashboard, MySessions (crew/visibility, gated delete), Clubs/Groups
  (create/invite/join), Boats (edit + photo crop), Devices (register + assignments), Profile.
- **M3 — Admin + events.** Events (regatta/raceday/race CRUD, perm-gated), Admin (cleanup, user.manage).
- **M4 — Race replay dashboard.** Sub-slice: (a) tracks+map, (b) charts+cursor, (c) playback+timeline,
  (d) leaderboard/VMG/laylines, (e) wind/polar overlays, (f) discussion+video.
- **M5 — Coach fold-in.** Port `web/coach/*` → `pages/app/Coach.tsx` + `components/coach/*`.
- **M6 — Deploy cutover.** Repoint static mount to `frontend/dist`, update `deploy.sh`, add CloudFront
  `/api/*` behavior, delete the `frontend/old/` tree (legacy `*.html`, `coach/`, `assets/`, stub); invalidate `/*`.

## Verification
Local: `SAILFRAMES_COOKIE_SECURE=0 … uvicorn backend.main:app --port 8000` + `cd frontend && npm run dev`.
Confirm DevTools shows `sf_access`/`sf_refresh` (HttpOnly) + `sf_csrf` (readable); a mutation carries
`X-SF-CSRF==sf_csrf`; deleting `sf_access` triggers exactly one `POST /api/auth/refresh` then a replay.
Per-milestone smoke:
- **M0:** register→login sets 3 cookies; `/me` 200; `/capabilities` matches shape; nav matches caps;
  anon hitting `/app/*` → `/login?redirect=`; logout clears cookies.
- **M1:** public pages load anonymously; private session → 403 → login CTA; fleet health renders.
- **M2:** create club/group/boat with CSRF; invite hidden unless club owner; session delete hidden
  without `session.delete`; private vs club device gating; nav updates after joining a club (`refreshMe`).
- **M3:** race create blocked (UI + server 403) without `race.create`; scoped `club_admin` limited to own club.
- **M4:** map/charts/timeline stay synced while scrubbing + at 1x/2x/4x; overlays toggle; video seek
  follows cursor; React profiler flat during playback.
- **M5:** coach login/review/print; coach auth isolated from member session.
- **M6:** SPA served at `/`; deep-link reload `/races/123` works (fallback); `/api/*` still routed;
  no 500s from removed assets.

## Key files
- New: everything under `frontend/` (tree above; `frontend/src/`).
- Backend touch (done for M0): `backend/routers/auth.py`, `backend/auth/permissions.py`
  (`effective_capabilities`), `backend/auth/__init__.py` (export); `backend/main.py` (CORS allow-list
  done; static mount repoint pending M6).
- Infra: `infrastructure/deploy.sh` (`build_frontend`, `deploy_website`, drop `config.js` shim), CloudFront `/api/*`.
- Delete at cutover (M6): the whole `frontend/old/` tree (legacy `*.html`, `assets/`, `coach/`,
  `config.js`, and the deprecated `frontend/old/frontend/` React stub).
- Reference to mirror: `…/formandopercorsi-frontend/src/pages/MainContent.tsx`, `…/src/utils/{api.ts,IsAuth.tsx}`.
- Vanilla to port: `web/assets/js/utils/time-sync.js`, `web/assets/js/components/{map-view,chart-panel,timeline,video-player}.js`, `web/assets/js/boat-classes.js`.

## Notes / risks
- **Scope:** the race dashboard (11.4k lines) is the bulk of the effort — M4 is by far the largest and
  should be sub-sliced as above; M0–M3 deliver the whole new user system quickly.
- **Coach Google auth** stays a separate flow from the member cookie auth (bridged or coach-scoped) — do
  not try to unify them in this pass.
- Native-readiness now = keeping `services/`, `types/`, `utils/api.ts`, auth logic framework-agnostic;
  extract to a shared package only when the native app actually starts.
