import { useTranslation } from "react-i18next";
import { useWindAt } from "@/hooks/useWindAt";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { fmtDateTime } from "@/utils/format";

/** Closest-in-time observation for a coordinate: resolves (or auto-creates)
 * the nearest station, then reads the cache around `at`. Used by session/race
 * pages that have GPS but no wind data of their own — see
 * backend/services/wind_lookup.py for the station resolution tiers. */
export function WindCard({ lat, lng, at }: { lat: number; lng: number; at?: string | null }) {
  const { t } = useTranslation();
  const { data, isLoading } = useWindAt(lat, lng, at);

  if (isLoading) return null; // don't block the page on a best-effort card
  if (!data) return null;
  const { station, observation: closest } = data;

  return (
    <Card title={`${t("nav.wind", "Wind")} — ${station.name ?? station.provider}`}>
      {isLoading ? (
        <Spinner />
      ) : !closest ? (
        <p className="sf-muted">{t("common.none")}</p>
      ) : (
        <div className="sf-tablewrap">
          <table className="sf-table">
            <tbody>
              <tr>
                <th>TWD</th>
                <td>{closest.twd_deg != null ? `${closest.twd_deg}°` : "—"}</td>
                <th>TWS</th>
                <td>{closest.tws_kts != null ? `${closest.tws_kts} kn` : "—"}</td>
                <th>Gust</th>
                <td>{closest.gust_kts != null ? `${closest.gust_kts} kn` : "—"}</td>
              </tr>
              <tr>
                <th colSpan={2}>{t("common.date")}</th>
                <td colSpan={4} className="sf-muted">
                  {fmtDateTime(closest.observed_at)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
