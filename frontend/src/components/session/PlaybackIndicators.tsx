import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useTimeState } from "@/stores/timeController";
import { buildCumulativeDistances, indexAt, pointAt, type Track } from "@/components/race/raceModel";
import { vmgAt } from "@/utils/vmgSeries";
import { fmtDistance, fmtKnots } from "@/utils/format";
import type { VmgPoint } from "@/types";
import styles from "./PlaybackIndicators.module.css";

// Live readout of speed/VMG/TWA/distance-so-far at the current playback
// cursor — 4 tiles in a row on desktop, 2×2 on mobile (see PlaybackIndicators.module.css).
export function PlaybackIndicators({ track, vmg }: { track: Track; vmg?: VmgPoint[] | null }) {
  const { t } = useTranslation();
  const { cursor } = useTimeState();
  const cumDist = useMemo(() => buildCumulativeDistances(track), [track]);

  const speed = pointAt(track, cursor)?.sog ?? null;
  const at = vmgAt(vmg, cursor);
  const idx = indexAt(track, cursor);
  const distanceM = idx >= 0 ? cumDist[idx] : 0;

  return (
    <div className={styles.indicators}>
      <div className={styles.tile}>
        <span className={styles.label}>{t("race.speed")}</span>
        <span className={styles.value}>{fmtKnots(speed)}</span>
      </div>
      <div className={styles.tile}>
        <span className={styles.label}>{t("sessions.vmg")}</span>
        <span className={styles.value}>{fmtKnots(at?.vmg_kts)}</span>
      </div>
      <div className={styles.tile}>
        <span className={styles.label}>TWA</span>
        <span className={styles.value}>
          {at?.twa_deg != null ? `${Math.abs(at.twa_deg).toFixed(0)}°` : "—"}
        </span>
      </div>
      <div className={styles.tile}>
        <span className={styles.label}>{t("sessions.distance")}</span>
        <span className={styles.value}>{fmtDistance(distanceM)}</span>
      </div>
    </div>
  );
}
