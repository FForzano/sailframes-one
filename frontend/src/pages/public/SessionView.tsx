import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { sessionsService } from "@/services/sessions.service";
import { useResource } from "@/hooks/useResource";
import { fmtDuration, fmtShortDate } from "@/utils/format";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";

// Read-only session detail. A private session the caller can't see returns 404
// from the API (deliberately — see backend), which we render as a not-found /
// login CTA rather than confirming the session exists.
export function SessionView() {
  const { t } = useTranslation();
  const { deviceId = "", date = "" } = useParams();
  const { data, loading, error } = useResource(
    () => sessionsService.get(deviceId, date),
    [deviceId, date],
  );

  if (loading) return <Spinner full />;

  if (error) {
    const notFound = error.toLowerCase().includes("not found");
    return (
      <div className="sf-page">
        <p className="sf-error">{notFound ? t("session.notFound") : error}</p>
        <p className="sf-muted">{t("session.notFoundHint")}</p>
        <Link to="/login" className="sf-btn sf-btn--primary">
          {t("auth.login")}
        </Link>
      </div>
    );
  }
  if (!data) return null;

  const rows: Array<[string, string]> = [
    [t("session.date"), fmtShortDate(data.date)],
    [t("session.boat"), String(data.boat ?? data.device_id)],
    [t("session.duration"), fmtDuration(data.duration_sec)],
    [t("sessions.visibility"), String(data.visibility ?? "public")],
    [t("session.sensors"), (data.sensors ?? []).join(", ") || "—"],
  ];

  return (
    <div className="sf-page">
      <Link to="/sessions" className="sf-back">← {t("sessions.title")}</Link>
      <h1 className="sf-page__title">{data.name || data.device_id}</h1>
      <Card>
        <dl className="sf-deflist">
          {rows.map(([k, v]) => (
            <div key={k} className="sf-deflist__row">
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        {(data.has_analysis || data.has_video) && (
          <p className="sf-muted sf-mt">
            {data.has_analysis && `✓ ${t("session.hasAnalysis")}  `}
            {data.has_video && `✓ ${t("session.hasVideo")}`}
          </p>
        )}
      </Card>
    </div>
  );
}
