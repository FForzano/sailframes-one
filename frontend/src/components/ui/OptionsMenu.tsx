import { Popover } from "@/components/ui/Popover";

export interface OptionsMenuItem {
  label: string;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

/** Generic "⋮" options menu — a small anchored dropdown of action items.
 * Reused wherever a card/row needs more actions than fit as inline buttons. */
export function OptionsMenu({ items }: { items: OptionsMenuItem[] }) {
  return (
    <Popover
      panelClassName="sf-optionsmenu__panel"
      trigger={({ open, toggle }) => (
        <button
          className="sf-btn sf-btn--ghost sf-btn--sm"
          aria-label="Options"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={toggle}
        >
          ⋮
        </button>
      )}
    >
      {({ close }) =>
        items.map((it, i) => (
          <button
            key={i}
            type="button"
            role="menuitem"
            disabled={it.disabled}
            className={`sf-optionsmenu__item ${it.danger ? "sf-optionsmenu__item--danger" : ""}`}
            onClick={() => {
              close();
              it.onClick();
            }}
          >
            {it.label}
          </button>
        ))
      }
    </Popover>
  );
}
