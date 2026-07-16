# Native apps (iOS/Android)

The existing React/Vite/TS SPA (`frontend/`) is wrapped in
[Capacitor](https://capacitorjs.com/) to produce iOS 14+ and Android 8+
native shells. The web app is unaffected: Capacitor config
(`frontend/capacitor.config.ts`) and the generated `frontend/ios/`/
`frontend/android/` native projects are only touched at native build time,
never by `vite dev`/`vite build`.

## Why Bearer auth for native

The web app authenticates via httpOnly cookies (`sf_access`/`sf_refresh`,
see `backend/routers/auth.py`), which depends on same-origin proxying — the
Vite dev proxy locally, nginx in production (`frontend/vite.config.ts`).
A Capacitor WebView has no such proxy and talks cross-origin to the real
backend host, where cookie jars (especially iOS's) aren't reliable.

So native uses `Authorization: Bearer <jwt>` instead: `backend/auth/
permissions.py`'s `current_user()` accepts a Bearer header first, falling
back to the cookie for web. Refresh works the same way — web relies on the
httpOnly `sf_refresh` cookie, native gets `refresh_token` in the
`/auth/login`/`/auth/refresh` response body and persists it in Keychain/
Keystore-backed secure storage (`frontend/src/services/nativeAuth.ts`,
using `@aparajita/capacitor-secure-storage` — never `@capacitor/
preferences`, which is unencrypted, and never localStorage). This module is
dynamically imported so it never lands in the web JS bundle.

## Building

```bash
cd frontend
npm install

# One-time native project setup (already done if android/ or ios/ exist):
npx cap add ios
npx cap add android

# Every build: point at the real backend origin (no /api proxy in a WebView).
cp .env.native.example .env.native   # edit VITE_API_BASE for real
set -a && source .env.native && set +a
npm run build
npx cap sync

npm run cap:open:ios      # or: npm run cap:open:android
```

`VITE_API_BASE` must be `https://api.xgsail.com/api` in production — the
dedicated Cloudflare Tunnel route straight to `backend:8000` (see
`deploy/README.md`), not `https://xgsail.com/api` (that goes through the
frontend's nginx and its 10 MB upload cap). The backend also needs the
WebView's origin in `SAILFRAMES_CORS_ORIGINS` (`capacitor://localhost` on
iOS, `https://app.xgsail.com` on Android — see `server.hostname` in
`capacitor.config.ts`, a dedicated purely-virtual hostname that doesn't need
to exist in DNS, set so password managers recognize the native app via
base-domain matching instead of "localhost") — already the default in
`deploy/docker-compose.prod.yml`'s `backend` service, but required if
you're pointing at a different backend (e.g. local dev over a LAN IP).

Minimum OS targets: Android 8 (`minSdkVersion 26` in
`android/variables.gradle`, set after `cap add android`) and iOS 14 (Xcode
deployment target, set after `cap add ios`).

## GPX share-target flow

Sharing a `.gpx` file from another app (e.g. Waterspeed) into XGSail:

1. **Android**: `AndroidManifest.xml`'s `MainActivity` needs an extra
   `<intent-filter>` for `ACTION_SEND`/`ACTION_VIEW` matching
   `application/gpx+xml` and the `.gpx` extension — add this by hand after
   `cap add android` (Capacitor doesn't generate it).
2. **iOS**: requires a **Share Extension Xcode target** + an **App Group**
   (`group.com.xgsail.app`) shared with the main app. This is a manual step
   that cannot be scripted by `cap sync`:
   - Needs a paid Apple Developer Program membership (App Groups
     entitlement is gated behind it).
   - In Xcode: File → New → Target → Share Extension.
   - Enable "App Groups" capability on both the main app and extension
     targets, same group ID.
   - The extension's `Info.plist` needs a custom exported UTType
     (`UTExportedTypeDeclarations`) for `.gpx`, since it isn't a
     system-registered type.
   - The extension's `ShareViewController.swift` copies the shared file
     into the App Group's shared container and hands off to the main app
     (custom URL scheme or shared-container polling on foreground).
   - Redo/review this whenever the iOS project structure changes — it does
     **not** ship via OTA (native code is explicitly excluded from OTA
     bundles, see `docs/ota-updates.md`).
3. `frontend/src/hooks/useShareTarget.ts` (native-only, no-ops on web)
   listens for `@capgo/capacitor-share-target`'s `shareReceived` event,
   reads the file via `@capacitor/filesystem`, and wraps it as a `File`.
4. `AppShell` navigates to `/diario/activities/import` when a share
   arrives; `ImportPage` (now accepting either a picked file or the shared
   one from the same hook) drives the existing `POST /imports` → `PUT
   upload_url` → `POST /imports/{id}/complete` flow unchanged.

## Background GPS recording ("Registra" tab)

The native-only "Registra" tab (`frontend/src/pages/registra/RegistraPage.tsx`,
gated behind `Capacitor.isNativePlatform()` in `AppShell.tsx`) records a GPS
track from the phone, including with the screen locked, sampling roughly once
a minute (`frontend/src/services/nativeRecording.ts`). This needs
`@capacitor-community/background-geolocation` — the only plugin in this
stack that can run an Android foreground service with a persistent
notification (`@capacitor/geolocation` cannot run in the background at all).
Like the GPX share-target, this is native code that **does not ship via
OTA** (see `docs/ota-updates.md`) — bump `min_native_version_android/ios`
after releasing a build that includes it, same mechanism as "Forcing a
native update" below.

1. **Android**: after `cap add android` / `cap sync`, add to
   `AndroidManifest.xml`: `ACCESS_BACKGROUND_LOCATION`,
   `FOREGROUND_SERVICE`, and (API 34+) `FOREGROUND_SERVICE_LOCATION`
   permissions, plus the notification channel the plugin's foreground
   service posts to. Verify the plugin's installed major version matches
   this project's Capacitor major (`frontend/package.json`) — community
   plugins can lag a Capacitor release.
2. **iOS**: `NSLocationAlwaysAndWhenInUseUsageDescription` in `Info.plist`
   and `UIBackgroundModes: location` — both manual edits after `cap add
   ios`, not generated by `cap sync`.
3. Sampling cadence is enforced in JS, not by the plugin: the watcher
   callback in `nativeRecording.ts` only persists a fix once
   `SAMPLE_INTERVAL_MS` (60s) has elapsed since the last saved one, since
   the plugin itself has no "once a minute" mode.
4. Recordings are stored locally first (a newline-delimited point log under
   `@capacitor/filesystem`'s `Directory.Data`, turned into real GPX XML only
   once, when the recording is stopped) and uploaded on demand through the
   existing `/api/imports` GPX pipeline — no backend changes were needed for
   the upload itself. Reassigning an already-uploaded standalone recording to
   an activity/regatta uses a new endpoint,
   `POST /api/sessions/{id}/attach-to-activity`
   (`backend/routers/sessions.py`), scoped to standalone (auto-created
   `solo`) sessions only.

## Testing without a paid Apple account

Android has no such gate — build and run on an emulator or device, share a
`.gpx` file from any app, and confirm it lands in the import wizard. Do
this first; it exercises the whole pipeline (share → hook → import →
backend) except the iOS Share Extension itself.

## Forcing a native update

OTA (`docs/ota-updates.md`) can only ship JS/HTML/CSS/asset changes — never
native code, plugins, or `capacitor.config.ts`. When a fix *does* need one of
those (e.g. the `minSdkVersion`/`AndroidManifest.xml`/`server.hostname`
changes made when this app was first set up), OTA can't reach installs still
on the old native build, so there needs to be a way to force them onto a real
store update instead.

- `AppConfigORM` (`backend/db/models/app_config.py`) is a singleton settings
  row seeded on startup (`auth.seed.seed_app_config`) with
  `min_native_version_android`/`min_native_version_ios` both `None` — i.e. no
  gate, by default. The two platforms are separate fields, not one shared
  value, since Android and iOS release cadences are independent (App Store
  review can lag a same-day Play Store rollout by days) — never compare an
  Android install against the iOS minimum or vice versa.
- `GET /api/app-config` is intentionally **public** (no auth): the native app
  calls it via `NativeVersionGate` (`frontend/src/components/native/
  NativeVersionGate.tsx`), wrapping the whole tree in `main.tsx` *before*
  `AuthProvider`, so a logged-out user on a blocked version never even
  reaches the login screen. It picks the field matching
  `Capacitor.getPlatform()` and compares it against `@capacitor/app`'s
  `App.getInfo().version` (the native versionName/CFBundleShortVersionString)
  and renders a full-screen "update required" block instead of the app if
  the installed version is lower. A backend-unreachable check fails open
  (never locks out a working app over a transient network error).
- `PATCH /api/app-config` (superadmin-only, `AdminPage`'s "App settings"
  card) is how you actually flip the switch — takes effect immediately, no
  redeploy needed, since every native launch re-checks it.
- Web is entirely unaffected — `NativeVersionGate` is a no-op off
  `Capacitor.isNativePlatform()`.
