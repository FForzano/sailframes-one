import { useMemo } from "react";
import { useAuth } from "./useAuth";
import type { Capabilities } from "@/types";

// Capability predicates derived from GET /api/auth/capabilities. `can()` mirrors
// the backend's global-vs-scoped permission logic exactly (see
// _user_has_permission), so the UI and server agree on what to show. The server
// still authorizes every mutation — these only gate visibility.
export interface CapabilityHelpers {
  caps: Capabilities | null;
  isSuperadmin: boolean;
  can: (perm: string, clubId?: number | null) => boolean;
  ownsClub: (clubId: number) => boolean;
  memberOfClub: (clubId: number) => boolean;
  memberOfGroup: (groupId: number) => boolean;
  isBoatOwner: (boatId: string) => boolean;
  isBoatSkipper: (boatId: string) => boolean;
  canManageAnyBoat: boolean;
  canManageAnyClub: boolean;
}

export function useCapabilities(): CapabilityHelpers {
  const { caps } = useAuth();
  return useMemo(() => {
    const isSuperadmin = caps?.user.is_superadmin ?? false;
    const m = caps?.memberships;

    const can = (perm: string, clubId?: number | null): boolean => {
      if (isSuperadmin) return true;
      if (!caps) return false;
      if (caps.permissions.global.includes(perm)) return true;
      if (clubId != null) {
        return caps.permissions.byClub[String(clubId)]?.includes(perm) ?? false;
      }
      // No club scope given: true if ANY club grants it.
      return Object.values(caps.permissions.byClub).some((keys) =>
        keys.includes(perm),
      );
    };

    return {
      caps: caps ?? null,
      isSuperadmin,
      can,
      ownsClub: (id) => isSuperadmin || (m?.clubsOwned.includes(id) ?? false),
      memberOfClub: (id) => m?.clubsMember.includes(id) ?? false,
      memberOfGroup: (id) => m?.groups.includes(id) ?? false,
      isBoatOwner: (id) => m?.boatsOwner.includes(id) ?? false,
      isBoatSkipper: (id) => m?.boatsSkipper.includes(id) ?? false,
      canManageAnyBoat:
        isSuperadmin ||
        (m ? m.boatsOwner.length + m.boatsSkipper.length > 0 : false) ||
        can("boat.edit"),
      canManageAnyClub:
        isSuperadmin || (m ? m.clubsOwned.length > 0 : false),
    };
  }, [caps]);
}
