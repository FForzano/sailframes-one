export function Spinner({ full = false }: { full?: boolean }) {
  return (
    <div className={full ? "sf-spinner sf-spinner--full" : "sf-spinner"} role="status" aria-label="Loading">
      <div className="sf-spinner__dot" />
    </div>
  );
}
