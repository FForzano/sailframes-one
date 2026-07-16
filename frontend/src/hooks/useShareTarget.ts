import { useCallback, useSyncExternalStore } from "react";
import { Capacitor } from "@capacitor/core";
import { Filesystem } from "@capacitor/filesystem";
import { CapacitorShareTarget, type SharedFile } from "@capgo/capacitor-share-target";

// Native-only: the OS share sheet (Android "Share to XGSail", iOS Share
// Extension) hands a shared GPX file to the app via this plugin. The file
// is turned into a normal `File` object so it can flow through the exact
// same import pipeline as a manually-picked file
// (services/imports.ts + api/media.ts), per CLAUDE.md's "no duplicated
// logic" — see pages/diario/ImportPage.tsx, which accepts this as a prop.
//
// State lives in a tiny module-level store (not component state) because
// the share can arrive before the import route is even mounted: AppShell
// subscribes to trigger navigation, ImportPage subscribes to consume the
// file — both need the same value regardless of where they sit in the tree.

let pendingFile: File | null = null;
const listeners = new Set<() => void>();

function setPendingFile(file: File | null) {
  pendingFile = file;
  listeners.forEach((l) => l());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

function getSnapshot() {
  return pendingFile;
}

/** Reads a shared file's bytes via the Filesystem plugin and wraps them as
 * a `File`, so downstream code never has to know about native URIs. */
async function toFile(shared: SharedFile): Promise<File> {
  const { data } = await Filesystem.readFile({ path: shared.uri });
  const blob =
    typeof data === "string"
      ? await (await fetch(`data:${shared.mimeType};base64,${data}`)).blob()
      : data;
  return new File([blob], shared.name, { type: shared.mimeType || "application/octet-stream" });
}

let listenerRegistered = false;

function ensureListenerRegistered() {
  if (listenerRegistered || !Capacitor.isNativePlatform()) return;
  listenerRegistered = true;
  void CapacitorShareTarget.addListener("shareReceived", (event) => {
    const gpx = event.files.find((f) => f.name.toLowerCase().endsWith(".gpx"));
    if (!gpx) return;
    void toFile(gpx).then(setPendingFile);
  });
}

/** Exposes the most recently shared GPX file (native only — always `null`
 * on web). Call `clearPendingShare()` once it's been consumed (handed off
 * to the import flow) so a stale file doesn't reappear on next mount. */
export function useShareTarget(): { pendingFile: File | null; clearPendingShare: () => void } {
  ensureListenerRegistered();
  const file = useSyncExternalStore(subscribe, getSnapshot);
  const clearPendingShare = useCallback(() => setPendingFile(null), []);
  return { pendingFile: file, clearPendingShare };
}
