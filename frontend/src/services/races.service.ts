import { api } from "@/utils/api";
import type { RaceSummary, Regatta } from "@/types";

export const racesService = {
  listRegattas: () =>
    api.get<{ regattas: Regatta[] }>("/regattas").then((r) => r.regattas),

  getRegatta: (id: string) =>
    api.get<Regatta & { races: RaceSummary[] }>(`/regattas/${id}`),

  listRaces: (params?: { regatta_id?: string; date?: string }) => {
    const qs = new URLSearchParams();
    if (params?.regatta_id) qs.set("regatta_id", params.regatta_id);
    if (params?.date) qs.set("date", params.date);
    const suffix = qs.toString() ? `?${qs}` : "";
    return api.get<{ races: RaceSummary[] }>(`/races${suffix}`).then((r) => r.races);
  },
};
