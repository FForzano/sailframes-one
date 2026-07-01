import type { CapabilityHelpers } from "@/hooks/useCapabilities";

// A Guard decides whether an authenticated user may see a route. Composed with
// withAuth (which first enforces authentication). Keep these aligned with the
// backend's require_permission gates — the server is still the real authority.
export type Guard = (h: CapabilityHelpers) => boolean;

export const requireSuperadmin: Guard = (h) => h.isSuperadmin;

export const requirePerm =
  (perm: string, clubId?: number): Guard =>
  (h) =>
    h.can(perm, clubId);

export const requireBoatManager: Guard = (h) => h.canManageAnyBoat;

export const requireClubManager: Guard = (h) => h.canManageAnyClub;

export const requireEventsAccess: Guard = (h) =>
  h.isSuperadmin ||
  h.can("regatta.manage") ||
  h.can("raceday.manage") ||
  h.can("race.create");

export const requireAdminArea: Guard = (h) =>
  h.isSuperadmin || h.can("admin") || h.can("user.manage");
