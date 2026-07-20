import { useToast } from "@/hooks/useToast";
import { Spinner } from "@/components/ui/Spinner";
import styles from "./ToastViewport.module.css";

export function ToastViewport() {
  const { toasts, dismiss } = useToast();
  if (toasts.length === 0) return null;
  return (
    <div className={styles.toasts} aria-live="polite">
      {toasts.map((t) => (
        <button
          key={t.id}
          className={`${styles.toast} ${styles[t.kind]}`}
          onClick={() => dismiss(t.id)}
        >
          {t.pending && <Spinner inline />}
          {t.message}
        </button>
      ))}
    </div>
  );
}
