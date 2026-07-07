import type { SailingRole } from "@/types";

// Mirrors the DB check constraint (backend/db/models/session.py
// SESSION_SAILING_ROLES) exactly — kept in sync manually, same pattern as
// utils/markRoles.ts.
export const SAILING_ROLES: SailingRole[] = ["skipper", "crew", "guest"];
