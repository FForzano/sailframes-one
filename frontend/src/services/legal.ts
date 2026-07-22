import { api } from "@/api/client";
import type { LegalMetadata } from "@/types";

export const legalKeys = {
  metadata: ["legal", "metadata"] as const,
};

export const legalService = {
  /** Current versions + effective dates of the legal documents (public). */
  metadata: () => api.get<LegalMetadata>("/legal"),

  /** Record (re-)acceptance of the current Terms and/or Privacy Policy. */
  accept: (body: { terms_and_conditions: boolean; privacy_policy: boolean }) =>
    api.post("/auth/accept-legal", body),
};
