export type BoatRole = "owner" | "skipper" | "crew" | "viewer";

export interface BoatMember {
  user_id: number;
  role: BoatRole;
  created_at?: string;
}

export interface Boat {
  boat_id: string;
  name: string;
  type: string;
  sail_number: string;
  club: string;
  club_id?: number | null;
  loa_m?: number | null;
  members: BoatMember[];
  notes: string;
  created_at?: string;
  updated_at?: string;
}

export interface BoatWrite {
  boat_id?: string;
  name?: string;
  type?: string;
  sail_number?: string;
  club?: string;
  club_id?: number | null;
  loa_m?: number | null;
  notes?: string;
}
