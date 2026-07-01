import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCapabilities } from "@/hooks/useCapabilities";
import { appNav, visibleEntries } from "@/data/navConfig";

// Mobile/tablet bottom tab bar — the touch-first counterpart of the Sidebar,
// and the shape a future native app will mirror. Capped to the first few
// capability-visible entries so the bar stays thumb-friendly.
const MAX_TABS = 5;

export function ActionBar() {
  const { t } = useTranslation();
  const caps = useCapabilities();
  const entries = visibleEntries(appNav, caps).slice(0, MAX_TABS);

  return (
    <nav className="sf-actionbar" aria-label="Personal area">
      {entries.map((e) => (
        <NavLink
          key={e.to}
          to={e.to}
          end={e.to === "/app"}
          className="sf-actionbar__tab"
        >
          <span className="sf-actionbar__glyph" aria-hidden>
            {e.glyph}
          </span>
          <span className="sf-actionbar__label">{t(e.labelKey)}</span>
        </NavLink>
      ))}
    </nav>
  );
}
