import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// Global loading counter — begin()/end() pairs so overlapping async work keeps
// the spinner up until the last one finishes.
export interface LoadingContextValue {
  active: boolean;
  begin: () => void;
  end: () => void;
}

export const LoadingContext = createContext<LoadingContextValue | null>(null);

export function LoadingProvider({ children }: { children: ReactNode }) {
  const [count, setCount] = useState(0);
  const begin = useCallback(() => setCount((c) => c + 1), []);
  const end = useCallback(() => setCount((c) => Math.max(0, c - 1)), []);
  const value = useMemo(
    () => ({ active: count > 0, begin, end }),
    [count, begin, end],
  );
  return <LoadingContext.Provider value={value}>{children}</LoadingContext.Provider>;
}
