import { api } from "@/api/client";
import type { AppConfig } from "@/types";

export const appConfigKeys = {
  root: ["app-config"] as const,
};

export const appConfigService = {
  // Public — no auth required (the native app checks this before login).
  get: () => api.get<AppConfig>("/app-config"),
  update: (body: Partial<AppConfig>) => api.patch<AppConfig>("/app-config", body),
};
