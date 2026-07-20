import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Capacitor } from "@capacitor/core";
import { App as CapacitorApp } from "@capacitor/app";
import { appConfigService } from "@/services/appConfig";
import { Spinner } from "@/components/ui/Spinner";
import styles from "./NativeVersionGate.module.css";

// Must match capacitor.config.ts's appId.
const ANDROID_PACKAGE_ID = "com.xgsail.app";
const PLAY_STORE_URL = `https://play.google.com/store/apps/details?id=${ANDROID_PACKAGE_ID}`;

/** "1.4.0" < "1.10.0" done numerically per segment, not lexically — good
 * enough for the plain x.y.z versions @capacitor/app reports, no need for
 * full semver (pre-release tags, build metadata) here. */
function isBelowMinVersion(installed: string, min: string): boolean {
  const a = installed.split(".").map((n) => parseInt(n, 10) || 0);
  const b = min.split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] ?? 0;
    const y = b[i] ?? 0;
    if (x !== y) return x < y;
  }
  return false;
}

/** Blocks the native app entirely when the installed version is below the
 * superadmin-set minimum (`/app-config`, AdminPage) — the OTA update path
 * (docs/ota-updates.md) can never ship native code/plugin/capacitor.config.ts
 * changes, so this is the only way to force a real store update for those.
 * Runs before AuthProvider, wrapping the whole app in main.tsx, so a
 * logged-out user on a blocked version never even reaches the login screen.
 * No-op on web — there's no "native version" concept there. */
export function NativeVersionGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [blocked, setBlocked] = useState(false);
  const [checked, setChecked] = useState(!Capacitor.isNativePlatform());

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let cancelled = false;
    void (async () => {
      try {
        const [config, info] = await Promise.all([appConfigService.get(), CapacitorApp.getInfo()]);
        // Android/iOS ship independently (App Store review can lag a
        // same-day Play Store rollout), so each platform has its own
        // minimum — never cross-compare an Android install against
        // min_native_version_ios or vice versa.
        const minVersion =
          Capacitor.getPlatform() === "ios"
            ? config.min_native_version_ios
            : config.min_native_version_android;
        if (!cancelled && minVersion && isBelowMinVersion(info.version, minVersion)) {
          setBlocked(true);
        }
      } catch {
        // Backend unreachable at launch: fail open rather than locking users
        // out of an already-working app over a transient network error.
      } finally {
        if (!cancelled) setChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!checked) return <Spinner full />;

  if (blocked) {
    return (
      <div className={styles.updateRequired}>
        <h1>{t("updateRequired.title")}</h1>
        <p>{t("updateRequired.body")}</p>
        {Capacitor.getPlatform() === "android" && (
          <a href={PLAY_STORE_URL} className="sf-btn sf-btn--primary">
            {t("updateRequired.cta")}
          </a>
        )}
      </div>
    );
  }

  return <>{children}</>;
}
