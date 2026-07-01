import { api } from "@/utils/api";
import type { Group } from "@/types";

export const groupsService = {
  list: () => api.get<{ groups: Group[] }>("/groups").then((r) => r.groups),
  listMine: () =>
    api.get<{ groups: Group[] }>("/groups?member=me").then((r) => r.groups),
  get: (id: number) => api.get<Group>(`/groups/${id}`),
  create: (name: string, description?: string, default_session_visibility = "private") =>
    api.post<Group>("/groups", { name, description, default_session_visibility }),
  invite: (groupId: number, userId: number, role = "member", status = "invited") =>
    api.post<Group>(`/groups/${groupId}/members`, { user_id: userId, role, status }),
  join: (groupId: number) => api.post<Group>(`/groups/${groupId}/join`),
};
