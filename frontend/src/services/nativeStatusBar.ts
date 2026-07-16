import { Capacitor } from "@capacitor/core";
import { StatusBar, Style } from "@capacitor/status-bar";

// Android (API 35+, targetSdkVersion 36 here) defaults to edge-to-edge,
// drawing the WebView under the status bar/notch — a problem on devices
// with a punch-hole or camera cutout. setOverlaysWebView(false) makes the
// status bar reserve its own strip instead of overlaying content; the
// matching background color keeps that strip visually part of the app
// rather than a stray black/white bar. The web bundle never imports this
// module (see contexts/AuthContext.tsx's nativeAuth for the same pattern).
export async function initNativeStatusBar(): Promise<void> {
  if (!Capacitor.isNativePlatform()) return;
  await StatusBar.setOverlaysWebView({ overlay: false });
  await StatusBar.setBackgroundColor({ color: "#0b1f33" });
  await StatusBar.setStyle({ style: Style.Dark });
}
