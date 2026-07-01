// A boat class is either a legacy free-text string or the structured object the
// race-edit form now emits. `boatClassLabel()` in utils normalizes both.
export type BoatClass = string | { id?: string; name?: string; loa_m?: number };

export interface Regatta {
  regatta_id: string;
  name: string;
  venue?: string;
  boat_class?: BoatClass;
  start_date?: string;
  end_date?: string;
  nor_url?: string;
  si_url?: string;
  website_url?: string;
}

export interface RaceSummary {
  race_id: string;
  name?: string;
  date?: string;
  start_time?: string;
  regatta_id?: string | null;
  raceday_id?: string | null;
}
