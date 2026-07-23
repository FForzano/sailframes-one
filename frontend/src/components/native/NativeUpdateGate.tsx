import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { CapacitorUpdater, type DownloadEvent } from "@capgo/capacitor-updater";
import { activeRecordingId } from "@/services/nativeRecording";
import styles from "./NativeUpdateGate.module.css";

// Guards concurrent update attempts (e.g. an appStateChange firing while
// the mount check is still in flight).
let checking = false;

/** Downloads and applies the latest OTA bundle (docs/ota-updates.md) if one
 * is available, unless a phone-GPS recording is in progress — reloading the
 * WebView mid-recording would drop `nativeRecording`'s in-memory `active`
 * watcher reference (it isn't persisted/rehydrated on restart), silently
 * orphaning the in-progress track. Re-checked right before `set()` too,
 * since a recording can start while the bundle is downloading. E1
 * (BLE-device) recordings don't need this guard — the device, not the app,
 * is the source of truth for those (see RegistraPage's E1RecordingControl),
 * so a reload just reconnects and re-reads status, no state lost.
 * Calling CapacitorUpdater.set() reloads the WebView and never resolves. */
async function tryApplyUpdate(onProgress?: (percent: number) => void): Promise<void> {
  if (checking || activeRecordingId() !== null) return;
  checking = true;
  let downloadListener: { remove: () => void } | undefined;
  try {
    if (onProgress) {
      downloadListener = await CapacitorUpdater.addListener("download", (state: DownloadEvent) => {
        onProgress(state.percent);
      });
    }

    const latest = await CapacitorUpdater.getLatest();
    if (!latest.url || latest.kind === "up_to_date" || latest.kind === "blocked") return;

    onProgress?.(0);
    const bundle = await CapacitorUpdater.download({ url: latest.url, version: latest.version });
    if (activeRecordingId() !== null) return;
    await CapacitorUpdater.set({ id: bundle.id });
  } finally {
    downloadListener?.remove();
    checking = false;
  }
}

/** Blocks the native app on a logo + progress screen while a pending OTA
 * update is applied on cold start, so a newly published update is live on
 * THIS launch instead of only becoming visible after one full
 * open-close-reopen cycle. Also re-checks silently (no blocking screen)
 * every time the app returns to foreground, so an update lands even for an
 * app left open in the background rather than only at the next cold start
 * — see `tryApplyUpdate` for the recording guard that protects an
 * in-progress phone-GPS recording either way. Runs before everything else
 * in main.tsx, including NativeVersionGate — capacitor.config.ts sets
 * `autoUpdate: "off"` so this manual flow is the only place that checks for
 * and applies updates (no competing background check on the same launch).
 * Calling CapacitorUpdater.set() reloads the WebView and destroys this JS
 * context; the reloaded bundle re-runs main.tsx from scratch, and this gate
 * then finds no further update and renders children normally.
 * No-op on web — there's no bundle-update concept there. */
export function NativeUpdateGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [ready, setReady] = useState(!Capacitor.isNativePlatform());
  const [progress, setProgress] = useState<number | null>(null);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let cancelled = false;

    void tryApplyUpdate((percent) => {
      if (!cancelled) setProgress(percent);
    })
      .catch(() => {
        // Update server unreachable/bundle invalid: fail open and continue
        // with the currently installed bundle rather than blocking launch.
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let listenerHandle: { remove: () => void } | undefined;

    void CapacitorApp.addListener("appStateChange", ({ isActive }) => {
      if (isActive) void tryApplyUpdate().catch(() => {});
    }).then((handle) => {
      listenerHandle = handle;
    });

    return () => {
      void listenerHandle?.remove();
    };
  }, []);

  if (!ready) {
    return (
      <div className={styles.updating}>
        <img src="/logo.svg" alt="" className={styles.logo} />
        <p>{t("nativeUpdate.body")}</p>
        {progress !== null && (
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>
    );
  }

  return <>{children}</>;
}
