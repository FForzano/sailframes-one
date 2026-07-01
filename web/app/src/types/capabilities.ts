import type { User } from "./auth";

// Shape of GET /api/auth/capabilities (see web/api/auth/permissions.py
// effective_capabilities). Permissions split global vs per-club, mirroring the
// backend's scoped-role logic so client and server agree.

export type PermissionKey =
  | "admin"
  | "regatta.manage"
  | "raceday.manage"
  | "race.create"
  | "race.edit"
  | "race.delete"
  | "boat.edit"
  | "session.delete"
  | "user.manage";

export interface RoleGrant {
  role: string;
  scope_club_id: number | null;
}

export interface Capabilities {
  user: User;
  roles: RoleGrant[];
  permissions: {
    global: string[];
    byClub: Record<string, string[]>; // clubId (as string) -> permission keys
  };
  memberships: {
    clubsOwned: number[];
    clubsMember: number[];
    groups: number[];
    boatsOwner: string[];
    boatsSkipper: string[];
  };
}
