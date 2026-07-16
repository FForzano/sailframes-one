import { useRef, useState } from "react";
import { useClickOutside } from "@/hooks/useClickOutside";

export interface MenuItem {
  label: string;
  onClick?: () => void;
  danger?: boolean;
  disabled?: boolean;
  /** Renders as a checkbox row instead of a button. */
  checked?: boolean;
  onCheckedChange?: (v: boolean) => void;
  /** Present → renders as an accordion row: click expands this item's own
   * sub-items in-place (indented, directly below), instead of firing
   * `onClick`. Nests to any depth (e.g. "Mostra su mappa" > "Andature" >
   * per-type checkboxes) — each level indents a bit further. */
  children?: MenuItem[];
}

export interface MenuSection {
  /** Bold section label with a divider above — omit for an unheaded group
   * (e.g. a single trailing danger item). */
  heading?: string;
  items: MenuItem[];
}

function MenuRow({ item, depth }: { item: MenuItem; depth: number }) {
  const [expanded, setExpanded] = useState(false);
  // Each nesting level indents a bit further (base padding + depth step).
  const indentStyle = depth > 0 ? { paddingLeft: `${0.6 + depth * 0.9}rem` } : undefined;

  if (item.children) {
    return (
      <>
        <button
          type="button"
          role="menuitem"
          aria-expanded={expanded}
          disabled={item.disabled}
          className="sf-menu__item sf-menu__item--accordion"
          style={indentStyle}
          onClick={() => setExpanded((v) => !v)}
        >
          <span>{item.label}</span>
          <span className="sf-menu__chevron">{expanded ? "▾" : "▸"}</span>
        </button>
        {expanded &&
          item.children.map((child, i) => (
            <MenuRow key={i} item={child} depth={depth + 1} />
          ))}
      </>
    );
  }

  if (item.onCheckedChange) {
    return (
      <label className="sf-check sf-menu__item" style={indentStyle}>
        <input
          type="checkbox"
          checked={!!item.checked}
          disabled={item.disabled}
          onChange={(e) => item.onCheckedChange?.(e.target.checked)}
        />
        <span>{item.label}</span>
      </label>
    );
  }

  return (
    <button
      type="button"
      role="menuitem"
      disabled={item.disabled}
      className={`sf-menu__item ${item.danger ? "sf-menu__item--danger" : ""}`}
      style={indentStyle}
      onClick={item.onClick}
    >
      {item.label}
    </button>
  );
}

/** Consolidated "⋮" action menu: grouped sections (optional bold heading +
 * divider) of buttons, checkboxes, or one-level accordion sub-items —
 * replaces the flat `OptionsMenu` for pages that outgrew a single list
 * (session detail: session actions, track actions incl. trim, per-type map
 * display toggles, delete). */
export function Menu({ sections }: { sections: MenuSection[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, () => setOpen(false));

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
        <div className="sf-options__panel sf-menu__panel" role="menu">
          {sections.map((section, i) => (
            <div key={i} className="sf-menu__section">
              {section.heading && <div className="sf-menu__heading">{section.heading}</div>}
              {section.items.map((item, j) => (
                <MenuRow
                  key={j}
                  depth={0}
                  item={{
                    ...item,
                    onClick: item.onClick && (() => {
                      setOpen(false);
                      item.onClick?.();
                    }),
                  }}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
