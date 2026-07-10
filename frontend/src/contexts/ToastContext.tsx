import {
  createContext,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ToastKind = "success" | "error" | "info" | "warning";
export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
  // A background job is still running for this toast — no auto-dismiss
  // timer is scheduled until `update()` resolves it (see SessionDetailPage's
  // reanalyze/wind-refresh polling).
  pending?: boolean;
}

export interface ToastContextValue {
  toasts: Toast[];
  // `durationMs: null` makes the toast sticky (no auto-dismiss) and marks
  // it `pending` — for a job that's still running. Returns the toast id so
  // the caller can `update()` it once the job resolves.
  notify: (message: string, kind?: ToastKind, durationMs?: number | null) => number;
  update: (id: number, message: string, kind?: ToastKind, durationMs?: number | null) => void;
  dismiss: (id: number) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, kind: ToastKind = "info", durationMs: number | null = 3500) => {
      const id = ++seq;
      setToasts((t) => [...t, { id, message, kind, pending: durationMs === null }]);
      if (durationMs !== null) window.setTimeout(() => dismiss(id), durationMs);
      return id;
    },
    [dismiss],
  );

  const update = useCallback(
    (id: number, message: string, kind: ToastKind = "info", durationMs: number | null = 3500) => {
      setToasts((t) => t.map((x) => (x.id === id ? { ...x, message, kind, pending: durationMs === null } : x)));
      if (durationMs !== null) window.setTimeout(() => dismiss(id), durationMs);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toasts, notify, update, dismiss }), [toasts, notify, update, dismiss]);
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}
