import { NavLink, Outlet } from "react-router-dom";
import type { ReactNode } from "react";

export interface SectionTab {
  to: string;
  label: string;
  end?: boolean;
}

/** Macro-section layout: sub-page tabs (real routes, not UI tabs) + outlet.
 * `header` renders below the tabs, above the outlet, on every sub-page of
 * the section (used by Gruppi for the shared invites/discovery strip) —
 * the tabs come first so they're the first scrollable element and can
 * stick to the top immediately (see `.sf-tabs` in global.css), rather than
 * a variable-height header transiting under a device notch/status bar
 * while it scrolls out of view. `footer` renders below the outlet (used by
 * Profilo for the mobile-only logout button). */
export function SectionLayout({
  tabs,
  header,
  footer,
}: {
  tabs: SectionTab[];
  header?: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="sf-section">
      <nav className="sf-tabs" aria-label="Section">
        {tabs.map((tab) => (
          <NavLink key={tab.to} to={tab.to} end={tab.end} className="sf-tab">
            {tab.label}
          </NavLink>
        ))}
      </nav>
      {header}
      <div className="sf-section__body">
        <Outlet />
      </div>
      {footer}
    </div>
  );
}
