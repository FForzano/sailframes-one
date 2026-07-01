// Snapshot each boat PUTs to raw/<boat>/_health.json. Fields are best-effort:
// firmware versions drift, so everything past the identity is optional.
export interface FleetHealth {
  boat_id?: string;
  fw?: string;
  battery_pct?: number;
  battery_v?: number;
  fix_quality?: number;
  sat_count?: number;
  logging?: boolean;
  wifi?: string;
  ip?: string;
  uptime_s?: number;
  free_heap?: number;
  unit_role?: string;
  timestamp?: string;
  [key: string]: unknown;
}

// A row in the fleet table: the boat id plus its snapshot (or a load error).
export interface FleetRow {
  boat: string;
  health: FleetHealth | null;
  error: string | null;
}
