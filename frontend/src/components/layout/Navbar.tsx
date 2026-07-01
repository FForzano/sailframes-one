import { Link, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { publicNav } from "@/data/navConfig";

// Public top bar (brand + public links + auth entry). Shown on public routes;
// the personal area uses the Sidebar/ActionBar instead.
export function Navbar() {
  const { t } = useTranslation();
  const { isAuth, user } = useAuth();

  return (
    <header className="sf-navbar">
      <Link to="/" className="sf-navbar__brand">
        SailFrames
      </Link>
      <nav className="sf-navbar__links">
        {publicNav.map((e) => (
          <NavLink key={e.to} to={e.to} end={e.to === "/"} className="sf-navlink">
            {t(e.labelKey)}
          </NavLink>
        ))}
      </nav>
      <div className="sf-navbar__actions">
        {isAuth ? (
          <Link to="/app" className="sf-btn sf-btn--primary">
            {user?.name || t("nav.myArea")}
          </Link>
        ) : (
          <Link to="/login" className="sf-btn sf-btn--primary">
            {t("auth.login")}
          </Link>
        )}
      </div>
    </header>
  );
}
