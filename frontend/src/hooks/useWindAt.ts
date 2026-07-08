import { useQuery } from "@tanstack/react-query";
import { windService, windKeys } from "@/services/wind";
import type { WindObservation, WindStation } from "@/types";

const WINDOW_HOURS = 12;

export interface WindAt {
  station: WindStation;
  observation: WindObservation | null;
}

/** Resolves (or auto-creates) the nearest wind station for a coordinate and
 * the cached observation closest to `at` (defaults to now). Requests an
 * explicit window around `at` rather than relying on the server's "last 72h"
 * default, so a session from weeks ago gets its own historical weather
 * instead of whatever happens to be most recent — see
 * backend/services/wind_lookup.backfill_historical for the cache-miss path. */
export function useWindAt(
  lat: number | undefined,
  lng: number | undefined,
  at?: string | null
): { data: WindAt | null; isLoading: boolean } {
  const hasCoords = lat != null && lng != null;
  const targetMs = at ? Date.parse(at) : Date.now();
  const start = new Date(targetMs - WINDOW_HOURS * 3600_000).toISOString();
  const end = new Date(targetMs + WINDOW_HOURS * 3600_000).toISOString();

  // Only forward an explicit `at` (a session/race's real time) to station
  // resolution — omitting it for "now" lookups keeps their real-sensor-first
  // behavior unchanged (see backend/services/wind_lookup.find_or_create_station).
  const station = useQuery({
    queryKey: hasCoords ? windKeys.nearest(lat, lng, at ?? undefined) : ["wind", "none"],
    queryFn: () => windService.nearest(lat!, lng!, at ?? undefined),
    enabled: hasCoords,
    staleTime: 60 * 60 * 1000, // an hour — the resolved station rarely changes
  });
  const observations = useQuery({
    queryKey: station.data
      ? windKeys.observations(station.data.id, `${start}|${end}`)
      : ["wind", "none"],
    queryFn: () => windService.observations(station.data!.id, { start, end, limit: 200 }),
    enabled: !!station.data,
  });

  if (!station.data) return { data: null, isLoading: hasCoords && station.isLoading };

  const closest = (observations.data ?? []).reduce<WindObservation | null>((best, o) => {
    if (!best) return o;
    return Math.abs(Date.parse(o.observed_at) - targetMs) <
      Math.abs(Date.parse(best.observed_at) - targetMs)
      ? o
      : best;
  }, null);

  return {
    data: { station: station.data, observation: closest },
    isLoading: observations.isLoading,
  };
}
