import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// Global surface for unexpected errors (a modal sink). Feature code should
// prefer inline handling + toasts; this catches the rest.
export interface AppError {
  message: string;
  code?: number;
}

export interface ErrorContextValue {
  error: AppError | null;
  raise: (error: AppError) => void;
  clear: () => void;
}

export const ErrorContext = createContext<ErrorContextValue | null>(null);

export function ErrorProvider({ children }: { children: ReactNode }) {
  const [error, setError] = useState<AppError | null>(null);
  const raise = useCallback((e: AppError) => setError(e), []);
  const clear = useCallback(() => setError(null), []);
  const value = useMemo(() => ({ error, raise, clear }), [error, raise, clear]);
  return <ErrorContext.Provider value={value}>{children}</ErrorContext.Provider>;
}
