import { api } from "@/api/client";
import type { PolarPoint, UUID } from "@/types";

export const polarKeys = {
  session: (id: UUID) => ["polar-points", "session", id] as const,
};

export const polarsService = {
  /** Empirical polar curve for one session (written by the processing
   * pipeline). Points across all TWS buckets; group by `tws_kts` to draw. */
  forSession: (sessionId: UUID) =>
    api.get<PolarPoint[]>(`/polar-points?session_id=${sessionId}`),
};
