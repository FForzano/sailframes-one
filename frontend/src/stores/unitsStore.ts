import { useSyncExternalStore } from "react";

// Speed/distance unit preference. The source of truth is the user's profile
// (users.unit_system, backend/db/models/user.py) so it follows the account
// across devices; this store is a localStorage-backed local cache of that
// value, kept in sync by AppShell on load, so number formatters
// (utils/format.ts) and any component can read/react to it synchronously
// without waiting on the /users/me query on every render.
export type UnitSystem = "nautical" | "metric";

const STORAGE_KEY = "sf-units";

class UnitsStore {
  private system: UnitSystem = (localStorage.getItem(STORAGE_KEY) as UnitSystem) || "nautical";
  private listeners = new Set<() => void>();

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getSnapshot = () => this.system;

  get(): UnitSystem {
    return this.system;
  }

  set(system: UnitSystem) {
    this.system = system;
    localStorage.setItem(STORAGE_KEY, system);
    this.listeners.forEach((l) => l());
  }
}

export const unitsStore = new UnitsStore();

export function useUnits(): UnitSystem {
  return useSyncExternalStore(unitsStore.subscribe, unitsStore.getSnapshot);
}
