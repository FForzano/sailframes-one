import { useEffect } from "react";
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
//
// Two route shapes: `/session/:deviceId/:date` (device-sourced sessions) and
// `/session/manual/:id` (manual/GPX-sourced sessions — they have no
// device_id/date, so they're addressed by the surrogate id instead).
export function SessionView() {
  const { t } = useTranslation();
  const { deviceId = "", date = "", id } = useParams();
  const manualId = id ? Number(id) : null;
  const { data, loading, error, reload } = useResource(
    () => (manualId != null ? sessionsService.getById(manualId) : sessionsService.get(deviceId, date)),
    [deviceId, date, manualId],
  );

  const processing = data?.processing_status === "pending" || data?.processing_status === "processing";

  // Poll while the GPX-parse/analysis background job is still running.
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(reload, 5000);
    return () => clearInterval(timer);
  }, [processing, reload]);

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
    [t("session.boat"), String(data.boat ?? data.device_id ?? "—")],
    [t("session.duration"), fmtDuration(data.duration_sec)],
    [t("sessions.visibility"), String(data.visibility ?? "public")],
    [t("session.sensors"), (data.sensors ?? []).join(", ") || "—"],
  ];

  return (
    <div className="sf-page">
      <Link to="/sessions" className="sf-back">← {t("sessions.title")}</Link>
      <h1 className="sf-page__title">{data.name || data.boat || data.device_id}</h1>
      <Card>
        {data.source === "manual" && (
          <p className="sf-muted sf-mt">
            {data.processing_status === "pending" && t("mysessions.statusPending")}
            {data.processing_status === "processing" && t("mysessions.statusProcessing")}
            {data.processing_status === "ready" && `✓ ${t("mysessions.statusReady")}`}
            {data.processing_status === "failed" &&
              `${t("mysessions.statusFailed")}: ${data.processing_error ?? ""}`}
            {processing && (
              <button type="button" className="sf-btn sf-btn--ghost sf-ml" onClick={reload}>
                {t("mysessions.refresh")}
              </button>
            )}
          </p>
        )}
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
