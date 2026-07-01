import { useMemo } from "react";
import { useTimeState } from "@/stores/timeController";
import { haversineMeters } from "@/utils/geo";
import { indexAt, type BoatTrack } from "./raceModel";

// Live standings at the cursor: distance sailed so far (proxy for progress) +
// current speed. Cumulative distance is precomputed once per track; each tick
// only binary-searches the cursor index.
export function Leaderboard({ tracks }: { tracks: BoatTrack[] }) {
  const { cursor } = useTimeState();

  const cum = useMemo(() => {
    const map: Record<string, number[]> = {};
    for (const tr of tracks) {
      const arr = new Array(tr.pts.length).fill(0);
      for (let i = 1; i < tr.pts.length; i++) {
        arr[i] =
          arr[i - 1] +
          haversineMeters(tr.pts[i - 1].lat, tr.pts[i - 1].lon, tr.pts[i].lat, tr.pts[i].lon);
      }
      map[tr.id] = arr;
    }
    return map;
  }, [tracks]);

  const rows = tracks
    .map((tr) => {
      const i = indexAt(tr, cursor);
      const dist = i >= 0 ? cum[tr.id][i] : 0;
      const sog = i >= 0 ? tr.pts[i].sog : 0;
      const heel = i >= 0 ? tr.pts[i].heel : undefined;
      return { tr, dist, sog, heel };
    })
    .sort((a, b) => b.dist - a.dist);

  return (
    <div className="sf-leaderboard">
      <h3 className="sf-section-title">Leaderboard</h3>
      <ol className="sf-lb">
        {rows.map((r, idx) => (
          <li key={r.tr.id} className="sf-lb__row">
            <span className="sf-lb__rank">{idx + 1}</span>
            <span className="sf-lb__dot" style={{ background: r.tr.color }} />
            <span className="sf-lb__name">{r.tr.name}</span>
            <span className="sf-lb__stat">{r.sog.toFixed(1)} kn</span>
            {r.heel != null && <span className="sf-lb__stat">{r.heel.toFixed(0)}°</span>}
            <span className="sf-lb__stat sf-muted">{(r.dist / 1000).toFixed(2)} km</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
