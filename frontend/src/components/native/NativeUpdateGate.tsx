import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Capacitor } from "@capacitor/core";
import { CapacitorUpdater, type DownloadEvent } from "@capgo/capacitor-updater";
import styles from "./NativeUpdateGate.module.css";

/** Blocks the native app on a logo + progress screen while a pending OTA
 * bundle (docs/ota-updates.md) is downloaded and applied, so a newly
 * published update is live on THIS launch instead of only becoming visible
 * after one full open-close-reopen cycle. Runs before everything else in
 * main.tsx, including NativeVersionGate — capacitor.config.ts sets
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
    let downloadListener: { remove: () => void } | undefined;

    void (async () => {
      try {
        downloadListener = await CapacitorUpdater.addListener("download", (state: DownloadEvent) => {
          if (!cancelled) setProgress(state.percent);
        });

        const latest = await CapacitorUpdater.getLatest();
        if (cancelled || !latest.url || latest.kind === "up_to_date" || latest.kind === "blocked") {
          return;
        }

        setProgress(0);
        const bundle = await CapacitorUpdater.download({ url: latest.url, version: latest.version });
        if (cancelled) return;
        // Reloads the WebView and never resolves — nothing after this runs.
        await CapacitorUpdater.set({ id: bundle.id });
      } catch {
        // Update server unreachable/bundle invalid: fail open and continue
        // with the currently installed bundle rather than blocking launch.
      } finally {
        if (!cancelled) setReady(true);
      }
    })();

    return () => {
      cancelled = true;
      downloadListener?.remove();
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
