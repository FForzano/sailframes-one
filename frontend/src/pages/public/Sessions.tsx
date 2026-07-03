import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { sessionsService } from "@/services/sessions.service";
import { useResource } from "@/hooks/useResource";
import { fmtDuration, fmtShortDate } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";

// Public sessions browser. The server already filters by visibility, so an
// anonymous caller sees only public sessions and a logged-in one also sees
// their own / crewed / club / group ones — no client-side gating needed.
export function Sessions() {
  const { t } = useTranslation();
  const { data, loading, error } = useResource(() => sessionsService.list(), []);

  if (loading) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  const sessions = data ?? [];

  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("sessions.title")}</h1>
      {sessions.length === 0 ? (
        <p className="sf-muted">{t("sessions.empty")}</p>
      ) : (
        <div className="sf-list">
          {sessions.map((s) => (
            <Link
              key={s.id}
              to={s.source === "manual" ? `/session/manual/${s.id}` : `/session/${s.device_id}/${s.date}`}
              className="sf-listrow"
            >
              <span className="sf-listrow__meta">{fmtShortDate(s.date)}</span>
              <span className="sf-listrow__main">
                {s.name || s.boat || s.device_id}
                {s.visibility && s.visibility !== "public" && (
                  <span className="sf-chip sf-chip--sm">{s.visibility}</span>
                )}
              </span>
              <span className="sf-listrow__meta">{fmtDuration(s.duration_sec)}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
