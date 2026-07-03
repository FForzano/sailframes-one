export type Visibility = "public" | "private" | "club" | "group";
export type SessionSource = "device" | "manual";
export type ProcessingStatus = "pending" | "processing" | "ready" | "failed";

export interface SessionSummary {
  id: number;
  device_id: string | null;
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
  source: SessionSource;
  processing_status: ProcessingStatus;
  processing_error?: string | null;
}

// The full manifest is broad and evolving; keep the known fields typed and
// allow the rest through rather than modelling every backfilled key.
export interface SessionDetail extends SessionSummary {
  [key: string]: unknown;
}
