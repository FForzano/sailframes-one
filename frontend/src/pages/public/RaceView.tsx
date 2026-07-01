import { useEffect, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { raceDataService } from "@/services/racedata.service";
import { useResource } from "@/hooks/useResource";
import { timeController } from "@/stores/timeController";
import { buildTracks, timeBounds } from "@/components/race/raceModel";
import { MapView } from "@/components/race/MapView";
import { SpeedChart } from "@/components/race/SpeedChart";
import { Timeline } from "@/components/race/Timeline";
import { Leaderboard } from "@/components/race/Leaderboard";
import { Spinner } from "@/components/ui/Spinner";
import { fmtShortDate } from "@/utils/format";

// Race replay dashboard (M4). Fetches race meta + time-aligned GPS/IMU, builds
// per-boat tracks, seeds the shared time controller, and composes the
// map / speed chart / timeline / leaderboard around it. Playback state lives in
// the controller store; the heavy arrays stay out of React state.
export function RaceView() {
  const { t } = useTranslation();
  const { raceId = "" } = useParams();
  const { data, loading, error } = useResource(
    () =>
      Promise.all([
        raceDataService.getRace(raceId),
        raceDataService.getData(raceId, "gps,imu"),
      ]).then(([race, raceData]) => ({ race, raceData })),
    [raceId],
  );

  const tracks = useMemo(
    () => (data ? buildTracks(data.raceData) : []),
    [data],
  );

  useEffect(() => {
    if (!tracks.length) return;
    const [tMin, tMax] = timeBounds(tracks);
    timeController.pause();
    timeController.setBounds(tMin, tMax);
    return () => timeController.pause();
  }, [tracks]);

  if (loading) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;
  if (!data) return null;

  const marks = data.race.marks ?? [];
  const hasData = tracks.length > 0;

  return (
    <div className="sf-raceview">
      <div className="sf-raceview__head">
        <Link to="/races" className="sf-back">← {t("races.title")}</Link>
        <h1 className="sf-page__title">{data.race.name || raceId}</h1>
        <span className="sf-muted">{fmtShortDate(data.race.date)}</span>
      </div>

      {!hasData ? (
        <p className="sf-muted">{t("race.noData")}</p>
      ) : (
        <div className="sf-raceview__grid">
          <div className="sf-raceview__map">
            <MapView tracks={tracks} marks={marks} />
          </div>
          <aside className="sf-raceview__side">
            <Leaderboard tracks={tracks} />
          </aside>
          <div className="sf-raceview__timeline">
            <Timeline />
            <SpeedChart tracks={tracks} />
          </div>
        </div>
      )}
    </div>
  );
}
