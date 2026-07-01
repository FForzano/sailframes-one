export interface ClubMember {
  user_id: number;
  status: "invited" | "active";
  joined_at?: string;
}

export interface Club {
  id: number;
  name: string;
  owner_user_id?: number;
  default_session_visibility: string;
  created_at?: string;
  members: ClubMember[];
}

export interface GroupMember {
  user_id: number;
  role: "admin" | "member";
  status: "invited" | "active";
  joined_at?: string;
}

export interface Group {
  id: number;
  name: string;
  description?: string;
  created_by?: number;
  default_session_visibility: string;
  created_at?: string;
  members: GroupMember[];
}
