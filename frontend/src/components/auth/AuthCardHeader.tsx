import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import styles from "./auth.module.css";

/** Shared brand header for the login/register cards — links back to the landing page. */
export function AuthCardHeader() {
  const { t } = useTranslation();
  return (
    <Link to="/" className={styles.authcardHeader}>
      <img src="/logo.svg" alt="" className={styles.authcardLogo} />
      <h1 className={styles.authcardBrand}>XGSail</h1>
      <p className={styles.authcardTagline}>{t("common.tagline")}</p>
    </Link>
  );
}
