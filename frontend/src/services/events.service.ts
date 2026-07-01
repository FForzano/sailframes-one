import { api } from "@/utils/api";
import type { RaceSummary, Regatta } from "@/types";

// Race day (a day within a regatta grouping races).
export interface RaceDay {
  raceday_id: string;
  date: string;
  type: string;
  name?: string | null;
  regatta_id?: string | null;
  race_ids: string[];
}

export interface RegattaCreate {
  name: string;
  venue: string;
  boat_class: string;
  start_date: string;
  end_date: string;
}

export interface RaceCreate {
  name: string;
  date: string;
  start_time: string;
  end_time: string;
  regatta_id?: string;
  raceday_id?: string;
}

// Events management (regatta / raceday / race). Backend gates writes on
// require_admin — the UI shows this area per capabilities, the server decides.
export const eventsService = {
  createRegatta: (body: RegattaCreate) => api.post<Regatta>("/regattas", body),
  deleteRegatta: (id: string) => api.del(`/regattas/${id}`),

  listRacedays: (regattaId?: string) =>
    api
      .get<{ race_days: RaceDay[] }>(
        `/racedays${regattaId ? `?regatta_id=${encodeURIComponent(regattaId)}` : ""}`,
      )
      .then((r) => r.race_days),
  createRaceday: (body: { date: string; type?: string; name?: string; regatta_id?: string }) =>
    api.post<RaceDay>("/racedays", body),

  createRace: (body: RaceCreate) => api.post<RaceSummary>("/races", body),
  deleteRace: (id: string) => api.del(`/races/${id}`),
};
