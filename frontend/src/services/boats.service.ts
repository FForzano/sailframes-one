import { api } from "@/utils/api";
import type { Boat, BoatMember, BoatRole, BoatWrite } from "@/types";

export const boatsService = {
  list: () => api.get<{ boats: Boat[] }>("/boats").then((r) => r.boats),
  get: (id: string) => api.get<Boat>(`/boats/${id}`),
  create: (body: BoatWrite) => api.post<Boat>("/boats", body),
  update: (id: string, body: BoatWrite) => api.patch<Boat>(`/boats/${id}`, body),
  listMembers: (id: string) =>
    api.get<{ members: BoatMember[] }>(`/boats/${id}/members`).then((r) => r.members),
  addMember: (id: string, userId: number, role: BoatRole = "crew") =>
    api.post<Boat>(`/boats/${id}/members`, { user_id: userId, role }),
  setMemberRole: (id: string, userId: number, role: BoatRole) =>
    api.patch<Boat>(`/boats/${id}/members/${userId}`, { role }),
  removeMember: (id: string, userId: number) =>
    api.del<Boat>(`/boats/${id}/members/${userId}`),
};
