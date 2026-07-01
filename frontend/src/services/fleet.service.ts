import { api } from "@/utils/api";
import { ApiError } from "@/utils/api";
import type { FleetHealth, FleetRow } from "@/types";

// The six-boat fleet. Kept here (not hardcoded in the page) so a later config
// endpoint can replace it without touching UI.
export const FLEET_BOATS = ["E1", "E2", "E3", "E4", "E5", "E6"];

export const fleetService = {
  // Proxied through the API so MinIO/local stays private (see backend fleet.py).
  getHealth: (boat: string) =>
    api.get<FleetHealth>(`/fleet/health/${boat}`),

  // Plain-text boot.log (safeJson falls back to the raw string).
  getBootlog: (boat: string) => api.get<string>(`/fleet/bootlog/${boat}`),

  // Fetch every boat's snapshot in parallel; a missing/never-booted boat
  // surfaces as a row with an error rather than failing the whole table.
  loadAll: async (): Promise<FleetRow[]> =>
    Promise.all(
      FLEET_BOATS.map(async (boat): Promise<FleetRow> => {
        try {
          const health = await fleetService.getHealth(boat);
          return { boat, health, error: null };
        } catch (e) {
          const msg =
            e instanceof ApiError && e.status === 404
              ? "no snapshot"
              : e instanceof ApiError
                ? e.detail
                : String(e);
          return { boat, health: null, error: msg };
        }
      }),
    ),
};
