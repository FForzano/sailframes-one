import { useTranslation } from "react-i18next";
import { Card } from "@/components/ui/Card";
import { useClubContext } from "./ClubDetailLayout";

export function ClubOverview() {
  const { t } = useTranslation();
  const { club, stationedBoats } = useClubContext();

  return (
    <>
      <Card>
        <p className="sf-muted">{club.description}</p>
        <p className="sf-muted">
          {club.city ?? ""}{" "}
          {club.website && (
            <a href={club.website} target="_blank" rel="noreferrer">
              {club.website}
            </a>
          )}
        </p>
      </Card>

      {stationedBoats.length > 0 && (
        <Card title={t("gruppi.stationedBoats")}>
          <div className="sf-strip">
            {stationedBoats.map((b) => (
              <div key={b.id} className="sf-strip__item sf-strip__item--muted">
                <span>
                  <strong>{b.name}</strong>{" "}
                  <span className="sf-muted">{b.sail_number ?? ""}</span>
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}
