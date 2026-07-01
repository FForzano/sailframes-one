import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import { Card } from "@/components/ui/Card";

// Capability-aware personal home. A single shell for every role — the numbers
// and role chips below are driven entirely by GET /api/auth/capabilities, so
// members, club admins and superadmins all land here and simply see different
// access reflected.
export function Dashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { caps } = useCapabilities();
  const m = caps?.memberships;

  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("dashboard.title")}</h1>
      <p className="sf-muted">
        {t("dashboard.welcome", { name: user?.name || user?.email || "" })}
      </p>

      <Card title={t("dashboard.capabilitiesTitle")} className="sf-dash__card">
        <div className="sf-dash__roles">
          <span className="sf-dash__label">{t("dashboard.roles")}:</span>{" "}
          {caps && caps.roles.length > 0 ? (
            caps.roles.map((r, i) => (
              <span key={i} className="sf-chip">
                {r.role}
                {r.scope_club_id != null ? ` · club ${r.scope_club_id}` : ""}
              </span>
            ))
          ) : (
            <span className="sf-muted">{t("dashboard.noRoles")}</span>
          )}
        </div>

        <ul className="sf-dash__stats">
          <li>
            <span className="sf-dash__num">{m?.clubsOwned.length ?? 0}</span>
            {t("dashboard.clubsOwned")}
          </li>
          <li>
            <span className="sf-dash__num">{m?.clubsMember.length ?? 0}</span>
            {t("dashboard.clubsMember")}
          </li>
          <li>
            <span className="sf-dash__num">{m?.groups.length ?? 0}</span>
            {t("dashboard.groups")}
          </li>
          <li>
            <span className="sf-dash__num">{m?.boatsOwner.length ?? 0}</span>
            {t("dashboard.boats")}
          </li>
        </ul>
      </Card>
    </div>
  );
}
