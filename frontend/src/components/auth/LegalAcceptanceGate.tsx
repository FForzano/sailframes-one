import { useState } from "react";
import { Link } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { legalService } from "@/services/legal";
import { Button } from "@/components/ui/Button";
import styles from "./LegalAcceptanceGate.module.css";

/** Full-screen blocking gate shown to a logged-in user when the Terms and/or
 * Privacy Policy have changed since they last accepted (capabilities
 * `legal.needsAcceptance`). They must re-accept the outdated document(s) to
 * continue, or log out. Only the documents that actually changed are shown. */
export function LegalAcceptanceGate() {
  const { t } = useTranslation();
  const { caps, logout, refreshCaps } = useAuth();
  const legal = caps?.legal;
  const needTerms = legal?.terms.needsAcceptance ?? false;
  const needPrivacy = legal?.privacy.needsAcceptance ?? false;

  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const canSubmit = (!needTerms || acceptTerms) && (!needPrivacy || acceptPrivacy);

  const onSubmit = async () => {
    setBusy(true);
    setError(false);
    try {
      await legalService.accept({
        terms_and_conditions: needTerms,
        privacy_policy: needPrivacy,
      });
      await refreshCaps();
    } catch {
      setError(true);
      setBusy(false);
    }
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.card}>
        <h1 className={styles.title}>{t("legal.gate.title")}</h1>
        <p className={styles.body}>{t("legal.gate.body")}</p>

        {needTerms && (
          <label className="sf-check">
            <input
              type="checkbox"
              checked={acceptTerms}
              onChange={(e) => setAcceptTerms(e.target.checked)}
            />
            <span>
              <Trans
                i18nKey="legal.acceptTermsFull"
                components={{ termsLink: <Link to="/terms" target="_blank" rel="noreferrer" /> }}
              />
            </span>
          </label>
        )}
        {needPrivacy && (
          <label className="sf-check">
            <input
              type="checkbox"
              checked={acceptPrivacy}
              onChange={(e) => setAcceptPrivacy(e.target.checked)}
            />
            <span>
              <Trans
                i18nKey="legal.acceptPrivacyFull"
                components={{ privacyLink: <Link to="/privacy" target="_blank" rel="noreferrer" /> }}
              />
            </span>
          </label>
        )}

        {error && <p className="sf-form__error">{t("errors.generic")}</p>}

        <Button onClick={onSubmit} disabled={!canSubmit || busy} className={styles.accept}>
          {t("legal.gate.accept")}
        </Button>
        <button type="button" className={styles.logout} onClick={() => void logout()}>
          {t("auth.logout")}
        </button>
      </div>
    </div>
  );
}
