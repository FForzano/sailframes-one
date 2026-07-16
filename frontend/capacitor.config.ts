import type { CapacitorConfig } from "@capacitor/cli";

// Native shell config for the iOS/Android wrapper around the existing SPA.
// The web app is unaffected by any of this — Capacitor only reads this file
// during `cap sync`/native builds, never during `vite dev`/`vite build`.
//
// Minimum OS targets: Android 8 (API 26, set in android/variables.gradle
// after `cap add android`) and iOS 14 (set as the Xcode deployment target
// after `cap add ios`) — see docs/native-apps.md.
const config: CapacitorConfig = {
  appId: "com.xgsail.app",
  appName: "XGSail",
  webDir: "dist",
  android: { minWebViewVersion: 60 },
  plugins: {
    CapacitorUpdater: {
      // Points at the standalone ota-service (see ota-service/), never the
      // FastAPI backend — OTA bundles are unrelated to app data.
      updateUrl: "https://ota.xgsail.com/manifest.json",
      // Self-hosted: no Capgo cloud analytics endpoint.
      statsUrl: "",
      // Check for updates on launch rather than silently patching mid-session
      // — keeps update behavior visible/predictable for App Store review.
      autoUpdate: true,
      resetWhenUpdate: true,
    },
  },
};

export default config;
