import { api } from "@/utils/api";
import type { SessionDetail, SessionSummary, Visibility } from "@/types";

export interface CrewSlot {
  user_id?: number | null;
  guest_name?: string | null;
  boat_role?: string | null;
}

export interface SessionCrewEdit {
  crew: CrewSlot[];
  boat_id?: string;
  visibility?: Visibility;
  club_id?: number;
  group_id?: number;
}

export const sessionsService = {
  // Server filters by visibility — anonymous callers get only public sessions.
  list: () =>
    api
      .get<{ sessions: SessionSummary[] }>("/sessions")
      .then((r) => r.sessions),

  // 404 for a private session the caller can't see (never confirmed to exist).
  get: (deviceId: string, date: string) =>
    api.get<SessionDetail>(`/sessions/${deviceId}/${date}`),

  editCrew: (deviceId: string, date: string, body: SessionCrewEdit) =>
    api.patch<SessionDetail>(`/sessions/${deviceId}/${date}/crew`, body),

  // Backend gates deletion on require_admin / session.delete.
  remove: (deviceId: string, date: string) =>
    api.del<{ status: string }>(`/sessions/${deviceId}/${date}`),
};
