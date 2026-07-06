import { useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { timeController, useTimeState } from "@/stores/timeController";
import type { Track } from "./raceModel";

// Speed-over-ground chart, one line per track, with a cursor line synced to the
// shared time controller. Click/drag anywhere seeks. Recharts-based to stay
// visually consistent with the analysis charts.
const H = 160;

export function SpeedChart({ tracks }: { tracks: Track[] }) {
  const { tMin, tMax, cursor } = useTimeState();
  const [dragging, setDragging] = useState(false);

  // Merge every track's points onto a shared time axis (one column per track);
  // gaps are connected so tracks with different clocks still render one line.
  const { data, maxSog } = useMemo(() => {
    const byMs = new Map<number, Record<string, number>>();
    let mx = 1;
    for (const tr of tracks) {
      for (const p of tr.pts) {
        if (p.sog > mx) mx = p.sog;
        const row = byMs.get(p.ms) ?? { ms: p.ms };
        row[tr.id] = p.sog;
        byMs.set(p.ms, row);
      }
    }
    const rows = [...byMs.values()].sort((a, b) => a.ms - b.ms);
    return { data: rows, maxSog: mx };
  }, [tracks]);

  const seekTo = (label: unknown) => {
    if (typeof label === "number") timeController.seek(label);
  };

  return (
    <div>
      <span className="sf-muted" style={{ fontSize: "0.8rem" }}>
        0–{maxSog.toFixed(0)} kn
      </span>
      <ResponsiveContainer width="100%" height={H}>
        <LineChart
          data={data}
          margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
          onMouseDown={(s) => {
            setDragging(true);
            seekTo(s?.activeLabel);
          }}
          onMouseMove={(s) => dragging && seekTo(s?.activeLabel)}
          onMouseUp={() => setDragging(false)}
          onMouseLeave={() => setDragging(false)}
        >
          <XAxis dataKey="ms" type="number" domain={[tMin, tMax]} hide />
          <YAxis domain={[0, maxSog]} hide />
          {tracks.map((tr) => (
            <Line
              key={tr.id}
              type="monotone"
              dataKey={tr.id}
              stroke={tr.color}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
          <ReferenceLine x={cursor} stroke="#fff" strokeWidth={1} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
