// Shared date/number formatters (timezone-safe: full timestamps go through
// Date, bare YYYY-MM-DD dates are noon-anchored so they don't shift a day).

import { unitsStore } from "@/stores/unitsStore";

const KN_TO_KMH = 1.852;

export function fmtDate(date?: string | null): string {
  if (!date) return "—";
  const d = date.length === 10 ? new Date(date + "T12:00:00") : new Date(date);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(ts?: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtTime(ms: number): string {
  return new Date(ms).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function fmtDuration(sec?: number | null): string {
  if (!sec) return "—";
  const m = Math.round(sec / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function fmtDistance(m?: number | null): string {
  if (m == null) return "—";
  if (unitsStore.get() === "metric") {
    const km = m / 1000;
    return `${km >= 10 ? km.toFixed(1) : km.toFixed(2)} km`;
  }
  const nm = m / 1852;
  return nm >= 10 ? `${nm.toFixed(1)} nm` : `${nm.toFixed(2)} nm`;
}

/** Same conversion as `fmtDistance` but from a nautical-miles input (e.g.
 * `SessionLeg.distance_nm`, already in nm rather than raw meters). */
export function fmtDistanceNm(nm?: number | null): string {
  return fmtDistance(nm == null ? null : nm * 1852);
}

export function fmtKnots(k?: number | null): string {
  if (k == null) return "—";
  if (unitsStore.get() === "metric") return `${(k * KN_TO_KMH).toFixed(1)} km/h`;
  return `${k.toFixed(1)} kn`;
}

export function fmtSeconds(sec?: number | null): string {
  return sec == null ? "—" : `${sec.toFixed(1)} s`;
}

export function userLabel(u?: { first_name?: string | null; last_name?: string | null; email?: string } | null): string {
  if (!u) return "—";
  const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
  return name || u.email || "—";
}
