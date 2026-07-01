import { api } from "@/utils/api";
import type { Club } from "@/types";

export const clubsService = {
  list: () => api.get<{ clubs: Club[] }>("/clubs").then((r) => r.clubs),
  get: (id: number) => api.get<Club>(`/clubs/${id}`),
  create: (name: string, default_session_visibility = "private") =>
    api.post<Club>("/clubs", { name, default_session_visibility }),
  invite: (clubId: number, userId: number, status = "invited") =>
    api.post<Club>(`/clubs/${clubId}/members`, { user_id: userId, status }),
  join: (clubId: number) => api.post<Club>(`/clubs/${clubId}/join`),
};
