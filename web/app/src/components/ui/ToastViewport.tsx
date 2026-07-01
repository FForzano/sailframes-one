import { useToast } from "@/hooks/useToast";

export function ToastViewport() {
  const { toasts, dismiss } = useToast();
  if (toasts.length === 0) return null;
  return (
    <div className="sf-toasts" aria-live="polite">
      {toasts.map((t) => (
        <button
          key={t.id}
          className={`sf-toast sf-toast--${t.kind}`}
          onClick={() => dismiss(t.id)}
        >
          {t.message}
        </button>
      ))}
    </div>
  );
}
