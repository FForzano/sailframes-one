import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { BackLink } from "@/components/ui/BackLink";
import { legalKeys, legalService } from "@/services/legal";
import { terms } from "@/content/legal/terms";
import { LegalDocument } from "./LegalDocument";
import styles from "./legal.module.css";

export function TermsPage() {
  const { t } = useTranslation();
  const meta = useQuery({ queryKey: legalKeys.metadata, queryFn: legalService.metadata });

  return (
    <div className={styles.page}>
      <div className={styles.backRow}>
        <BackLink fallback="/" label={t("common.backHome")} />
      </div>
      <LegalDocument
        content={terms}
        version={meta.data?.terms.version}
        effectiveDate={meta.data?.terms.effective_date}
      />
    </div>
  );
}
