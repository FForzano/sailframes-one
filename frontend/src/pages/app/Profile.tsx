import { useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export function Profile() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { caps, isSuperadmin } = useCapabilities();

  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("nav.profile")}</h1>

      <Card title={t("profile.account")}>
        <dl className="sf-deflist">
          <div className="sf-deflist__row">
            <dt>{t("auth.name")}</dt>
            <dd>{user?.name || "—"}</dd>
          </div>
          <div className="sf-deflist__row">
            <dt>{t("auth.email")}</dt>
            <dd>{user?.email}</dd>
          </div>
          <div className="sf-deflist__row">
            <dt>{t("profile.role")}</dt>
            <dd>{isSuperadmin ? "superadmin" : caps?.roles.map((r) => r.role).join(", ") || t("dashboard.noRoles")}</dd>
          </div>
        </dl>
      </Card>

      <Card title={t("profile.language")}>
        <div className="sf-btnrow">
          <Button variant={i18n.language === "en" ? "primary" : "ghost"} onClick={() => i18n.changeLanguage("en")}>
            English
          </Button>
          <Button variant={i18n.language === "it" ? "primary" : "ghost"} onClick={() => i18n.changeLanguage("it")}>
            Italiano
          </Button>
        </div>
      </Card>

      <div className="sf-mt">
        <Button variant="danger" onClick={() => void logout()}>
          {t("auth.logout")}
        </Button>
      </div>
    </div>
  );
}
