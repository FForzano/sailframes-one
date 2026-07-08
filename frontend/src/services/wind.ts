import { api } from "@/api/client";
import type { UUID, WindObservation, WindStation } from "@/types";

export const windKeys = {
  stations: ["wind", "stations"] as const,
  observations: (id: UUID, params = "") => ["wind", "stations", id, "observations", params] as const,
  nearest: (lat: number, lng: number, at?: string) => ["wind", "nearest", lat, lng, at ?? "now"] as const,
};

export const windService = {
  listStations: () => api.get<WindStation[]>("/wind/stations"),
  createStation: (body: Partial<WindStation>) => api.post<WindStation>("/wind/stations", body),
  updateStation: (id: UUID, body: Partial<WindStation>) =>
    api.patch<WindStation>(`/wind/stations/${id}`, body),
  removeStation: (id: UUID) => api.del(`/wind/stations/${id}`),
  /** Newest-first, paginated (default: last 72h server-side, 200 rows). */
  observations: (id: UUID, opts: { start?: string; end?: string; limit?: number; offset?: number } = {}) => {
    const p = new URLSearchParams();
    if (opts.start) p.set("start", opts.start);
    if (opts.end) p.set("end", opts.end);
    if (opts.limit) p.set("limit", String(opts.limit));
    if (opts.offset) p.set("offset", String(opts.offset));
    const s = p.toString();
    return api.get<WindObservation[]>(`/wind/stations/${id}/observations${s ? `?${s}` : ""}`);
  },
  /** Get-or-create the best station for a coordinate (real sensor > grid
   * point > auto-created Open-Meteo point) — any authenticated user. Pass
   * `at` (a session/race's real time) so a real sensor with no historical
   * data for that date falls through to the Open-Meteo grid tier instead. */
  nearest: (lat: number, lng: number, at?: string) => {
    const p = new URLSearchParams({ lat: String(lat), lng: String(lng) });
    if (at) p.set("at", at);
    return api.get<WindStation>(`/wind/nearest?${p.toString()}`);
  },
};
