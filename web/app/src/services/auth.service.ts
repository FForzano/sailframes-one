import { api } from "@/utils/api";
import type { Capabilities, LoginResponse, User } from "@/types";

export const authService = {
  register: (email: string, password: string, name?: string) =>
    api.post<User>("/auth/register", { email, password, name }),

  login: (email: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { email, password }),

  logout: () => api.post<{ ok: boolean }>("/auth/logout"),

  me: () => api.get<User>("/auth/me"),

  capabilities: () => api.get<Capabilities>("/auth/capabilities"),
};
