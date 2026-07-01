// Time-aligned sensor payloads for the race replay (from /api/races/{id}/data).
export interface GpsPoint {
  t: string; // ISO timestamp
  lat: number;
  lon: number;
  sog?: number; // speed over ground (kt)
  cog?: number; // course over ground (deg)
}

export interface ImuPoint {
  t: string;
  heel?: number;
  pitch?: number;
}

export interface BoatSensors {
  gps?: GpsPoint[];
  imu?: ImuPoint[];
  wind?: Array<{ t: string; aws?: number; awa?: number }>;
}

export interface BoatData {
  boat?: { device_id: string; boat_name?: string; sail_number?: string };
  sensors?: BoatSensors;
  error?: string;
}

export interface RaceData {
  boats: Record<string, BoatData>;
}

export interface RaceMark {
  mark_id: string;
  name?: string;
  mark_type?: string;
  lat: number;
  lon: number;
}

export interface RaceDetail {
  race_id: string;
  name?: string;
  date?: string;
  start_time?: string;
  end_time?: string;
  boats?: Array<{ device_id: string; boat_name?: string; sail_number?: string }>;
  marks?: RaceMark[];
  [key: string]: unknown;
}
