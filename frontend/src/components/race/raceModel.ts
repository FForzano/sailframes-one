import type { RaceData } from "@/types/racedata";

// A boat's replay track: parsed points (ms epoch) + a stable display color.
export interface TrackPoint {
  ms: number;
  lat: number;
  lon: number;
  sog: number;
  heel?: number;
}
export interface BoatTrack {
  id: string;
  name: string;
  color: string;
  pts: TrackPoint[];
}

// Distinct, colorblind-ish palette assigned by boat order.
const PALETTE = ["#2f9be0", "#e0654f", "#3fbf7f", "#e0b24a", "#9b6fe0", "#4fd0e0"];

export function buildTracks(data: RaceData): BoatTrack[] {
  const tracks: BoatTrack[] = [];
  let i = 0;
  for (const [id, bd] of Object.entries(data.boats ?? {})) {
    if (bd.error || !bd.sensors?.gps?.length) {
      i++;
      continue;
    }
    const imu = bd.sensors.imu ?? [];
    // IMU heel aligned to nearest gps time is overkill for M4; index-pair when
    // lengths match, else skip heel.
    const pts: TrackPoint[] = bd.sensors.gps.map((p, idx) => ({
      ms: new Date(p.t).getTime(),
      lat: p.lat,
      lon: p.lon,
      sog: p.sog ?? 0,
      heel: imu.length === bd.sensors!.gps!.length ? imu[idx]?.heel : undefined,
    }));
    pts.sort((a, b) => a.ms - b.ms);
    tracks.push({
      id,
      name: bd.boat?.boat_name || id,
      color: PALETTE[i % PALETTE.length],
      pts,
    });
    i++;
  }
  return tracks;
}

// Nearest point at or before `ms` (no interpolation — marker sits on real fix).
export function pointAt(track: BoatTrack, ms: number): TrackPoint | null {
  const { pts } = track;
  if (!pts.length) return null;
  if (ms <= pts[0].ms) return pts[0];
  if (ms >= pts[pts.length - 1].ms) return pts[pts.length - 1];
  // Binary search for the last point <= ms.
  let lo = 0;
  let hi = pts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (pts[mid].ms <= ms) lo = mid;
    else hi = mid - 1;
  }
  return pts[lo];
}

// Index of the last point at or before `ms` (−1 if before the track starts).
export function indexAt(track: BoatTrack, ms: number): number {
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

export function timeBounds(tracks: BoatTrack[]): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const tr of tracks) {
    if (!tr.pts.length) continue;
    min = Math.min(min, tr.pts[0].ms);
    max = Math.max(max, tr.pts[tr.pts.length - 1].ms);
  }
  return Number.isFinite(min) ? [min, max] : [0, 0];
}
