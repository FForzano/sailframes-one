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

## Testing without a paid Apple account

Android has no such gate — build and run on an emulator or device, share a
`.gpx` file from any app, and confirm it lands in the import wizard. Do
this first; it exercises the whole pipeline (share → hook → import →
backend) except the iOS Share Extension itself.
