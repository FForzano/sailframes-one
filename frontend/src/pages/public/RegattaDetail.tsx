import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { racesService } from "@/services/races.service";
import { useResource } from "@/hooks/useResource";
import { boatClassLabel, fmtDateRange, fmtShortDate } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";

export function RegattaDetail() {
  const { t } = useTranslation();
  const { regattaId = "" } = useParams();
  const { data, loading, error } = useResource(
    () => racesService.getRegatta(regattaId),
    [regattaId],
  );

  if (loading) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;
  if (!data) return null;

  const cls = boatClassLabel(data.boat_class);
  const sub = [data.venue, cls, fmtDateRange(data.start_date, data.end_date)]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="sf-page">
      <Link to="/races" className="sf-back">← {t("races.title")}</Link>
      <h1 className="sf-page__title">{data.name}</h1>
      {sub && <p className="sf-muted">{sub}</p>}

      <h2 className="sf-section-title">{t("races.seriesRaces")}</h2>
      {data.races.length === 0 ? (
        <p className="sf-muted">{t("races.noRaces")}</p>
      ) : (
        <div className="sf-list">
          {data.races.map((r) => (
            <Link key={r.race_id} to={`/race/${r.race_id}`} className="sf-listrow">
              <span className="sf-listrow__meta">{fmtShortDate(r.date)}</span>
              <span className="sf-listrow__main">{r.name || "Race"}</span>
              <span className="sf-listrow__cta">{t("races.open")} →</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
