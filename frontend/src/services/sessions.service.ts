import { api } from "@/utils/api";
import type { SessionDetail, SessionSummary } from "@/types";

export const sessionsService = {
  // Server filters by visibility — anonymous callers get only public sessions.
  list: () =>
    api
      .get<{ sessions: SessionSummary[] }>("/sessions")
      .then((r) => r.sessions),

  // 404 for a private session the caller can't see (never confirmed to exist).
  get: (deviceId: string, date: string) =>
    api.get<SessionDetail>(`/sessions/${deviceId}/${date}`),
};
