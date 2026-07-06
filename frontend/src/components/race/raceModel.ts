import type { GpsPoint, RaceData } from "@/types";

// A replay track: parsed points (ms epoch) + a stable display color.
export interface TrackPoint {
  ms: number;
  lat: number;
  lon: number;
  sog: number;
}
export interface Track {
  id: string;
  name: string;
  color: string;
  pts: TrackPoint[];
}

// Distinct, colorblind-ish palette assigned by track order.
const PALETTE = ["#2f9be0", "#e0654f", "#3fbf7f", "#e0b24a", "#9b6fe0", "#4fd0e0"];

export function trackColor(i: number): string {
  return PALETTE[i % PALETTE.length];
}

// Sequential blue→cyan→green→yellow→red scale, used to color a track by
// speed (slow = blue, fast = red) instead of the flat per-track PALETTE color.
const SPEED_SCALE: Array<[number, [number, number, number]]> = [
  [0.0, [47, 107, 224]],
  [0.35, [47, 191, 224]],
  [0.6, [63, 191, 127]],
  [0.8, [224, 178, 74]],
  [1.0, [224, 79, 79]],
];

/** Maps `sog` to a color along `SPEED_SCALE`, normalized against [min, max]
 * (typically a single track's own speed range, so its full gradient is used
 * regardless of how fast the boat actually went). */
export function speedColor(sog: number, min: number, max: number): string {
  const t = max > min ? Math.min(1, Math.max(0, (sog - min) / (max - min))) : 0;
  for (let i = 1; i < SPEED_SCALE.length; i++) {
    const [t0, c0] = SPEED_SCALE[i - 1];
    const [t1, c1] = SPEED_SCALE[i];
    if (t <= t1) {
      const f = (t - t0) / (t1 - t0 || 1);
      const r = Math.round(c0[0] + (c1[0] - c0[0]) * f);
      const g = Math.round(c0[1] + (c1[1] - c0[1]) * f);
      const b = Math.round(c0[2] + (c1[2] - c0[2]) * f);
      return `rgb(${r},${g},${b})`;
    }
  }
  const last = SPEED_SCALE[SPEED_SCALE.length - 1][1];
  return `rgb(${last[0]},${last[1]},${last[2]})`;
}

/** [min, max] `sog` across a track's points (both 0 if empty). */
export function speedRange(track: Track): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const p of track.pts) {
    if (p.sog < min) min = p.sog;
    if (p.sog > max) max = p.sog;
  }
  return Number.isFinite(min) ? [min, max] : [0, 0];
}

/** One track from a processed GPS stream (canonical point shape
 * `{t, lat, lon, speed_kn, course}` — worker output / GPX parse). */
export function buildTrack(id: string, name: string, points: GpsPoint[], color: string): Track {
  const pts: TrackPoint[] = points
    .filter((p) => p.lat != null && p.lon != null)
    .map((p) => ({
      ms: Date.parse(p.t),
      lat: p.lat,
      lon: p.lon,
      sog: p.speed_kn ?? 0,
    }))
    .sort((a, b) => a.ms - b.ms);
  return { id, name, color, pts };
}

/** Tracks from `GET /races/{id}/data` — sessions keyed by id, boat embedded. */
export function buildTracks(data: RaceData): Track[] {
  const tracks: Track[] = [];
  let i = 0;
  for (const [sessionId, entry] of Object.entries(data.sessions ?? {})) {
    const gps = entry.sensors?.gps;
    if (!gps?.length) {
      i++;
      continue;
    }
    tracks.push(buildTrack(sessionId, entry.boat?.name ?? sessionId.slice(0, 8), gps, trackColor(i)));
    i++;
  }
  return tracks.filter((tr) => tr.pts.length > 0);
}

// Nearest point at or before `ms` (no interpolation — marker sits on real fix).
export function pointAt(track: Track, ms: number): TrackPoint | null {
  const i = indexAt(track, ms);
  if (i < 0) return track.pts[0] ?? null;
  return track.pts[i];
}

// Index of the last point at or before `ms` (−1 if before the track starts).
export function indexAt(track: Track, ms: number): number {
  const { pts } = track;
  if (!pts.length || ms < pts[0].ms) return -1;
  let lo = 0;
  let hi = pts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (pts[mid].ms <= ms) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

// Earth radius in meters, for the haversine distance used by the cumulative
// distance helper below.
const EARTH_R_M = 6371000;

function haversineM(a: TrackPoint, b: TrackPoint): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_R_M * Math.asin(Math.min(1, Math.sqrt(s)));
}

/** Cumulative distance (meters) from the track's start up to and including
 * each point — index-aligned with `track.pts`, for live "distance so far"
 * readouts during playback (paired with `indexAt`). */
export function buildCumulativeDistances(track: Track): number[] {
  const out: number[] = new Array(track.pts.length);
  let total = 0;
  for (let i = 0; i < track.pts.length; i++) {
    if (i > 0) total += haversineM(track.pts[i - 1], track.pts[i]);
    out[i] = total;
  }
  return out;
}

/** Median gap (ms) between consecutive fixes — used to size a sensible
 * step-forward/back jump for the playback transport controls. */
export function medianIntervalMs(track: Track): number {
  const { pts } = track;
  if (pts.length < 2) return 5000;
  const gaps = pts.slice(1).map((p, i) => p.ms - pts[i].ms).sort((a, b) => a - b);
  return gaps[Math.floor(gaps.length / 2)] || 5000;
}

export function timeBounds(tracks: Track[]): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const tr of tracks) {
    if (!tr.pts.length) continue;
    min = Math.min(min, tr.pts[0].ms);
    max = Math.max(max, tr.pts[tr.pts.length - 1].ms);
  }
  return Number.isFinite(min) ? [min, max] : [0, 0];
}
