import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { BackLink } from "@/components/ui/BackLink";
import { legalKeys, legalService } from "@/services/legal";
import { privacy } from "@/content/legal/privacy";
import { LegalDocument } from "./LegalDocument";
import styles from "./legal.module.css";

export function PrivacyPage() {
  const { t } = useTranslation();
  const meta = useQuery({ queryKey: legalKeys.metadata, queryFn: legalService.metadata });

  return (
    <div className={styles.page}>
      <div className={styles.backRow}>
        <BackLink fallback="/" label={t("common.backHome")} />
      </div>
      <LegalDocument
        content={privacy}
        version={meta.data?.privacy.version}
        effectiveDate={meta.data?.privacy.effective_date}
      />
    </div>
  );
}
