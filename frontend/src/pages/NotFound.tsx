import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function NotFound() {
  const { t } = useTranslation();
  return (
    <section className="sf-notfound">
      <h1>{t("notFound.title")}</h1>
      <p>{t("notFound.body")}</p>
      <Link to="/" className="sf-btn sf-btn--primary">
        {t("notFound.back")}
      </Link>
    </section>
  );
}
