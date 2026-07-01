import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";

export function Home() {
  const { t } = useTranslation();
  const { isAuth } = useAuth();

  return (
    <section className="sf-hero">
      <h1 className="sf-hero__title">{t("home.title")}</h1>
      <p className="sf-hero__tagline">{t("home.tagline")}</p>
      <div className="sf-hero__actions">
        <Link to="/races" className="sf-btn sf-btn--ghost">
          {t("home.browseRaces")}
        </Link>
        {isAuth ? (
          <Link to="/app" className="sf-btn sf-btn--primary">
            {t("home.openMyArea")}
          </Link>
        ) : (
          <Link to="/login" className="sf-btn sf-btn--primary">
            {t("home.getStarted")}
          </Link>
        )}
      </div>
    </section>
  );
}
