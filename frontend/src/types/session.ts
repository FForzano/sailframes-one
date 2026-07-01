export type Visibility = "public" | "private" | "club" | "group";

export interface SessionSummary {
  device_id: string;
  date: string;
  start_time?: string;
  end_time?: string;
  duration_sec?: number;
  duration_minutes?: number;
  sensors: string[];
  has_video?: boolean;
  has_analysis?: boolean;
  boat?: string;
  name?: string;
  session_id?: string;
  visibility?: Visibility;
  boat_id?: string | null;
}

// The full manifest is broad and evolving; keep the known fields typed and
// allow the rest through rather than modelling every backfilled key.
export interface SessionDetail extends SessionSummary {
  [key: string]: unknown;
}
