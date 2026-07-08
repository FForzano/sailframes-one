import type { Activity } from "@/types";

function timeOfDayKey(hour: number): "morning" | "afternoon" | "evening" | "night" {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 18) return "afternoon";
  if (hour >= 18 && hour < 22) return "evening";
  return "night";
}

/** Display name for an activity: its explicit `name` if the user set one,
 * else a friendly "Pomeriggio - 27 giugno" style label derived from
 * `started_at` (falls back to the type badge label, e.g. "Solo", if there's
 * no timestamp yet). */
export function activityDisplayName(
  a: Pick<Activity, "name" | "started_at" | "type">,
  t: (key: string) => string,
): string {
  if (a.name) return a.name;
  if (!a.started_at) return t(`activities.types.${a.type}`);
  const d = new Date(a.started_at);
  const period = t(`activities.timeOfDay.${timeOfDayKey(d.getHours())}`);
  const date = d.toLocaleDateString(undefined, { day: "numeric", month: "long" });
  return `${period} - ${date}`;
}
