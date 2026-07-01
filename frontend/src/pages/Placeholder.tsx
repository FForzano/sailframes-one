import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";

// Stand-in for routes whose real UI arrives in a later milestone (M1–M5). Keeps
// the route table and navigation complete so the shell can be exercised end to
// end during M0.
export function Placeholder({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="sf-page">
      <Card title={t(titleKey)}>
        <p className="sf-muted">
          <strong>{t("common.comingSoon")}.</strong> {t("common.comingSoonBody")}
        </p>
      </Card>
    </div>
  );
}
