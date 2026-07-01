import { api } from "@/utils/api";
import type { RaceData, RaceDetail } from "@/types/racedata";

export const raceDataService = {
  getRace: (raceId: string) => api.get<RaceDetail>(`/races/${raceId}`),

  getData: (raceId: string, sensors = "gps,imu") =>
    api.get<RaceData>(`/races/${raceId}/data?sensors=${encodeURIComponent(sensors)}`),
};
