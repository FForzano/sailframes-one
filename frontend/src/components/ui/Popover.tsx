import { useRef, useState, type ReactNode } from "react";
import { useClickOutside } from "@/hooks/useClickOutside";

/** Shared "anchored dropdown" shell: owns open state, the outside-click-to-
 * close behavior, and the `.sf-options`/`.sf-options__panel` chrome —
 * `trigger`/`children` supply whatever's inside (a "⋮" button + list of
 * items, an avatar + profile links, a "⚙" button + a single checkbox…).
 * Extracted so OptionsMenu/ProfileMenu/SpeedChart's popovers share one
 * implementation of the open/close plumbing instead of each re-declaring it. */
export function Popover({
  trigger,
  children,
  panelClassName,
  title,
}: {
  trigger: (state: { open: boolean; toggle: () => void }) => ReactNode;
  children: (state: { close: () => void }) => ReactNode;
  /** Extra class(es) on the panel, alongside the shared `sf-options__panel`. */
  panelClassName?: string;
  title?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, () => setOpen(false));
  const close = () => setOpen(false);

  return (
    <div className="sf-options" ref={ref} title={title}>
      {trigger({ open, toggle: () => setOpen((v) => !v) })}
      {open && (
        <div className={`sf-options__panel ${panelClassName ?? ""}`} role="menu">
          {children({ close })}
        </div>
      )}
    </div>
  );
}
