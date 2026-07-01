import { Link, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import { appNav, visibleEntries } from "@/data/navConfig";

// Desktop personal-area navigation. Entries are filtered by capabilities, so a
// single component serves every role.
export function Sidebar() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const caps = useCapabilities();
  const entries = visibleEntries(appNav, caps);

  return (
    <aside className="sf-sidebar">
      <Link to="/" className="sf-sidebar__brand">
        SailFrames
      </Link>
      <nav className="sf-sidebar__nav">
        {entries.map((e) => (
          <NavLink
            key={e.to}
            to={e.to}
            end={e.to === "/app"}
            className="sf-sidebar__link"
          >
            <span className="sf-sidebar__glyph" aria-hidden>
              {e.glyph}
            </span>
            {t(e.labelKey)}
          </NavLink>
        ))}
      </nav>
      <div className="sf-sidebar__foot">
        <span className="sf-sidebar__user">{user?.name || user?.email}</span>
        <button className="sf-btn sf-btn--ghost" onClick={() => void logout()}>
          {t("auth.logout")}
        </button>
      </div>
    </aside>
  );
}
