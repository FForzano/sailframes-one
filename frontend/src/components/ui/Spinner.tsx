import styles from "./Spinner.module.css";

export function Spinner({ full = false, inline = false }: { full?: boolean; inline?: boolean }) {
  const className = inline
    ? `${styles.spinner} ${styles.inline}`
    : full
      ? `${styles.spinner} ${styles.full}`
      : styles.spinner;
  return (
    <div className={className} role="status" aria-label="Loading">
      <div className={styles.dot} />
    </div>
  );
}
