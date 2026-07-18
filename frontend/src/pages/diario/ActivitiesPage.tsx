import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { activitiesService, activityKeys } from "@/services/activities";
import { UpcomingEventsBanner } from "@/components/diario/UpcomingEventsBanner";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { activityDisplayName } from "@/utils/activityName";
import { fmtDate } from "@/utils/format";

export function ActivitiesPage() {
  const { t } = useTranslation();
  const [type, setType] = useState("");
  const [mine, setMine] = useState(true);

  const activities = useQuery({
    queryKey: activityKeys.list({ type, mine: String(mine) }),
    queryFn: () => activitiesService.list({ type: type || undefined, mine }),
  });

  return (
    <>
      <UpcomingEventsBanner />
      <Card
        title={t("activities.title")}
        actions={
          <Link to="/diario/activities/import">
            <Button>{t("sessions.import")}</Button>
          </Link>
        }
      >
        <div className="sf-form__row" style={{ alignItems: "end" }}>
          <Select
            label={t("activities.type")}
            id="act-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">{t("common.none")}</option>
            <option value="race">{t("activities.types.race")}</option>
            <option value="training">{t("activities.types.training")}</option>
            <option value="solo">{t("activities.types.solo")}</option>
          </Select>
          <label className="sf-check">
            <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
            <span>{t("activities.mine")}</span>
          </label>
        </div>

        {activities.isLoading ? (
          <Spinner />
        ) : activities.data?.length === 0 ? (
          <EmptyState>{t("activities.empty")}</EmptyState>
        ) : (
          <div className="sf-activity-grid">
            {activities.data?.map((a) => (
              <Link key={a.id} to={`/diario/activities/${a.id}`} className="sf-activity-card">
                {a.thumbnail ? (
                  <img src={a.thumbnail.url} alt="" className="sf-activity-card__thumb" />
                ) : (
                  <span className="sf-activity-card__thumb sf-activity-card__thumb--empty" aria-hidden />
                )}
                <div className="sf-activity-card__body">
                  <strong>{activityDisplayName(a, t)}</strong>
                  <div className="sf-strip">
                    <span className="sf-badge">{t(`activities.types.${a.type}`)}</span>
                    <span className="sf-muted">{fmtDate(a.started_at)}</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
