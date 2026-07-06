import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { timeController, useTimeState } from "@/stores/timeController";
import { fmtKnots, fmtTime } from "@/utils/format";
import type { VmgPoint } from "@/types";
import type { Track } from "./raceModel";

// Speed-over-ground chart, one line per track, with a cursor line synced to
// the shared time controller. Click/drag anywhere seeks — it doubles as the
// playback scrubber. Optionally overlays the VMG series (toggle via the
// options popover) and shows a tap/hover tooltip with the values at that time.
const H = 160;

export function SpeedChart({ tracks, vmg }: { tracks: Track[]; vmg?: VmgPoint[] | null }) {
  const { t } = useTranslation();
  const { tMin, tMax, cursor } = useTimeState();
  const [dragging, setDragging] = useState(false);
  const [showVmg, setShowVmg] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);

  // Merge every track's points (and the VMG series) onto a shared time axis;
  // gaps are connected so tracks with different clocks still render one line.
  const { data, maxSog, maxVmg } = useMemo(() => {
    const byMs = new Map<number, Record<string, number>>();
    let mxSog = 1;
    let mxVmg = 1;
    for (const tr of tracks) {
      for (const p of tr.pts) {
        if (p.sog > mxSog) mxSog = p.sog;
        const row = byMs.get(p.ms) ?? { ms: p.ms };
        row[tr.id] = p.sog;
        byMs.set(p.ms, row);
      }
    }
    for (const v of vmg ?? []) {
      if (v.vmg_kts > mxVmg) mxVmg = v.vmg_kts;
      const ms = v.timestamp * 1000;
      const row = byMs.get(ms) ?? { ms };
      row.vmg = v.vmg_kts;
      byMs.set(ms, row);
    }
    const rows = [...byMs.values()].sort((a, b) => a.ms - b.ms);
    return { data: rows, maxSog: mxSog, maxVmg: mxVmg };
  }, [tracks, vmg]);

  const seekTo = (label: unknown) => {
    if (typeof label === "number") timeController.seek(label);
  };

  return (
    <div className="sf-chartpanel">
      <div className="sf-chartpanel__head">
        <span className="sf-muted" style={{ fontSize: "0.8rem" }}>
          0–{fmtKnots(maxSog)}
        </span>
        {!!vmg?.length && (
          <div className="sf-options">
            <button
              className="sf-btn sf-btn--ghost sf-btn--sm"
              aria-label="Chart options"
              onClick={() => setOptionsOpen((v) => !v)}
            >
              ⚙
            </button>
            {optionsOpen && (
              <div className="sf-options__panel">
                <label className="sf-check">
                  <input
                    type="checkbox"
                    checked={showVmg}
                    onChange={(e) => setShowVmg(e.target.checked)}
                  />
                  <span>{t("sessions.vmg")}</span>
                </label>
              </div>
            )}
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={H}>
        <AreaChart
          data={data}
          margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
          onMouseDown={(s) => {
            setDragging(true);
            seekTo(s?.activeLabel);
          }}
          onMouseMove={(s) => dragging && seekTo(s?.activeLabel)}
          onMouseUp={() => setDragging(false)}
          onMouseLeave={() => setDragging(false)}
          // Touch needs its own handlers — Recharts' touch support only
          // drives the tooltip, not these mouse callbacks, which otherwise
          // made mobile scrubbing need a first "activating" tap before drag.
          onTouchStart={(s) => seekTo(s?.activeLabel)}
          onTouchMove={(s) => seekTo(s?.activeLabel)}
        >
          <XAxis dataKey="ms" type="number" domain={[tMin, tMax]} hide />
          <YAxis yAxisId="sog" domain={[0, maxSog]} hide />
          {showVmg && <YAxis yAxisId="vmg" orientation="right" domain={[0, maxVmg]} hide />}
          <Tooltip
            labelFormatter={(ms) => (typeof ms === "number" ? fmtTime(ms) : "")}
            formatter={(v, name) => [
              fmtKnots(Number(v)),
              name === "vmg" ? t("sessions.vmg") : t("race.speed"),
            ]}
          />
          {tracks.map((tr) => (
            <Area
              key={tr.id}
              yAxisId="sog"
              type="monotone"
              dataKey={tr.id}
              stroke={tr.color}
              strokeWidth={1.5}
              fill={tr.color}
              fillOpacity={0.15}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
          {showVmg && (
            <Area
              yAxisId="vmg"
              type="monotone"
              dataKey="vmg"
              stroke="#e0b24a"
              strokeWidth={1.5}
              fill="#e0b24a"
              fillOpacity={0.15}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          )}
          <ReferenceLine yAxisId="sog" x={cursor} stroke="#fff" strokeWidth={1} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
