import type { BoatClass } from "@/types";

// Noon-anchored so a bare YYYY-MM-DD doesn't shift a day across timezones.
export function fmtShortDate(date?: string | null): string {
  if (!date) return "";
  return new Date(date + "T12:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function fmtDateRange(start?: string, end?: string): string {
  if (!start) return "";
  if (!end || end === start) return fmtShortDate(start);
  const startNoYear = new Date(start + "T12:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
  // Same year → drop the redundant year on the start side.
  if (start.slice(0, 4) === end.slice(0, 4)) {
    return `${startNoYear} – ${fmtShortDate(end)}`;
  }
  return `${fmtShortDate(start)} – ${fmtShortDate(end)}`;
}

export function fmtDuration(sec?: number): string {
  if (!sec) return "—";
  const m = Math.round(sec / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

// boat_class may be a legacy string or the structured {name,...} object.
export function boatClassLabel(bc?: BoatClass): string {
  if (!bc) return "";
  if (typeof bc === "string") return bc.trim();
  return (bc.name ?? "").trim();
}
