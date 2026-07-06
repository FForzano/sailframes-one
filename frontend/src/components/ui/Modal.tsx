import { useEffect, type ReactNode } from "react";

// Minimal accessible modal: Esc closes, backdrop click closes, body content
// is arbitrary. Feature forms live inside as children.
export function Modal({
  title,
  onClose,
  children,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="sf-modal__backdrop" onClick={onClose}>
      <div
        className="sf-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sf-modal__head">
          <h2 className="sf-modal__title">{title}</h2>
          <button className="sf-modal__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="sf-modal__body">{children}</div>
      </div>
    </div>
  );
}
