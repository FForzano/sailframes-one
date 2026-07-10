export function Spinner({ full = false, inline = false }: { full?: boolean; inline?: boolean }) {
  const className = inline ? "sf-spinner sf-spinner--inline" : full ? "sf-spinner sf-spinner--full" : "sf-spinner";
  return (
    <div className={className} role="status" aria-label="Loading">
      <div className="sf-spinner__dot" />
    </div>
  );
}
