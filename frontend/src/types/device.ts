export type OwnerType = "user" | "club";
export type DeviceType = "sailframes_e" | "sailframes_b" | "external";

export interface DeviceAssignment {
  id?: number;
  device_id: string;
  boat_id: string;
  regatta_id?: string | null;
  race_id?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  created_by?: number;
  created_at?: string;
}

export interface Device {
  device_id: string;
  name?: string | null;
  device_type: DeviceType;
  default_boat_id?: string | null;
  owner_type: OwnerType;
  registered_by?: number;
  owned_by_club_id?: number | null;
  status: "active" | "revoked";
  created_at?: string;
  last_seen_at?: string | null;
  assignments: DeviceAssignment[];
}

export interface DeviceRegister {
  name?: string;
  device_type?: DeviceType;
  owner_type: OwnerType;
  default_boat_id?: string;
  owned_by_club_id?: number;
}
