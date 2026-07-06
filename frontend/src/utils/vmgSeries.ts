import type { VmgPoint } from "@/types";

// Nearest VMG-series sample at or before `ms` (same binary-search shape as
// raceModel's `indexAt`, applied to the worker-native (seconds) VMG series).
export function vmgAt(series: VmgPoint[] | null | undefined, ms: number): VmgPoint | null {
  if (!series?.length) return null;
  const t = ms / 1000;
  if (t < series[0].timestamp) return null;
  let lo = 0;
  let hi = series.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (series[mid].timestamp <= t) lo = mid;
    else hi = mid - 1;
  }
  return series[lo];
}
