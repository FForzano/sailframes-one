import { useSyncExternalStore } from "react";

// Speed/distance unit preference, persisted like the language choice
// (i18n/index.ts) but with subscriber support so number formatters
// (utils/format.ts) and any component can react to a live change.
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
