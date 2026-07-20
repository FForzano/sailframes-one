import type { MarkRole } from "@/types";

// Mirrors the DB check constraint (backend/db/models/activity.py MARK_ROLES)
// exactly — kept in sync manually since it's a small, rarely-changing enum.
export const MARK_ROLES: MarkRole[] = [
  "pin",
  "rc",
  "windward",
  "leeward",
  "gate_port",
  "gate_stbd",
  "offset",
  "drill",
  "finish_pin",
  "finish_rc",
];
