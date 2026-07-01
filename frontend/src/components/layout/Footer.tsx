import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="sf-footer">
      <span>SailFrames — 10 Hz GNSS + IMU sailing analytics</span>
      <nav className="sf-footer__links">
        <Link to="/bom">{t("nav.bom")}</Link>
        <Link to="/battery">{t("nav.battery")}</Link>
        <a href="https://github.com/sailframes/core" target="_blank" rel="noopener noreferrer">
          GitHub
        </a>
      </nav>
      <span>Apache-2.0</span>
    </footer>
  );
}
