import { useEffect, useRef, useState } from "react";

export interface OptionsMenuItem {
  label: string;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

/** Generic "⋮" options menu — a small anchored dropdown of action items.
 * Reused wherever a card/row needs more actions than fit as inline buttons. */
export function OptionsMenu({ items }: { items: OptionsMenuItem[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  return (
    <div className="sf-options" ref={ref}>
      <button
        className="sf-btn sf-btn--ghost sf-btn--sm"
        aria-label="Options"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        ⋮
      </button>
      {open && (
        <div className="sf-options__panel sf-optionsmenu__panel" role="menu">
          {items.map((it, i) => (
            <button
              key={i}
              type="button"
              role="menuitem"
              disabled={it.disabled}
              className={`sf-optionsmenu__item ${it.danger ? "sf-optionsmenu__item--danger" : ""}`}
              onClick={() => {
                setOpen(false);
                it.onClick();
              }}
            >
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
