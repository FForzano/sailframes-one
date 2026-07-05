import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { windService, windKeys } from "@/services/wind";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { fmtDateTime } from "@/utils/format";
import type { WindObservation } from "@/types";

/** Closest-in-time observation for a coordinate: resolves (or auto-creates)
 * the nearest station, then reads its recent cache. Used by session/race
 * pages that have GPS but no wind data of their own — see
 * backend/services/wind_lookup.py for the station resolution tiers. */
export function WindCard({ lat, lng, at }: { lat: number; lng: number; at?: string | null }) {
  const { t } = useTranslation();

  const station = useQuery({
    queryKey: windKeys.nearest(lat, lng),
    queryFn: () => windService.nearest(lat, lng),
    staleTime: 60 * 60 * 1000, // an hour — the resolved station rarely changes
  });
  const observations = useQuery({
    queryKey: station.data ? windKeys.observations(station.data.id) : ["wind", "none"],
    queryFn: () => windService.observations(station.data!.id, { limit: 500 }),
    enabled: !!station.data,
  });

  if (station.isLoading) return null; // don't block the page on a best-effort card
  if (!station.data) return null;

  const targetMs = at ? Date.parse(at) : Date.now();
  const closest = (observations.data ?? []).reduce<WindObservation | null>((best, o) => {
    if (!best) return o;
    return Math.abs(Date.parse(o.observed_at) - targetMs) <
      Math.abs(Date.parse(best.observed_at) - targetMs)
      ? o
      : best;
  }, null);

  return (
    <Card title={`${t("nav.wind", "Wind")} — ${station.data.name ?? station.data.provider}`}>
      {observations.isLoading ? (
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
