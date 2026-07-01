import { useMemo, useRef } from "react";
import { timeController, useTimeState } from "@/stores/timeController";
import type { BoatTrack } from "./raceModel";

// SVG speed-over-ground chart, one polyline per boat, with a draggable cursor
// line synced to the shared time controller. Click/drag anywhere seeks.
const W = 1000;
const H = 180;

export function SpeedChart({ tracks }: { tracks: BoatTrack[] }) {
  const { tMin, tMax, cursor } = useTimeState();
  const svgRef = useRef<SVGSVGElement>(null);
  const span = Math.max(1, tMax - tMin);

  const { maxSog, paths } = useMemo(() => {
    let mx = 1;
    for (const tr of tracks) for (const p of tr.pts) if (p.sog > mx) mx = p.sog;
    const built = tracks.map((tr) => {
      const d = tr.pts
        .map((p, i) => {
          const x = ((p.ms - tMin) / span) * W;
          const y = H - (p.sog / mx) * H;
          return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(" ");
      return { id: tr.id, color: tr.color, d };
    });
    return { maxSog: mx, paths: built };
  }, [tracks, tMin, span]);

  const seekFromEvent = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    timeController.seek(tMin + frac * span);
  };

  const cursorX = ((cursor - tMin) / span) * W;

  return (
    <div className="sf-speedchart">
      <div className="sf-speedchart__scale">{maxSog.toFixed(0)} kn</div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="sf-speedchart__svg"
        onPointerDown={(e) => {
          (e.target as Element).setPointerCapture?.(e.pointerId);
          seekFromEvent(e.clientX);
        }}
        onPointerMove={(e) => e.buttons === 1 && seekFromEvent(e.clientX)}
      >
        {paths.map((p) => (
          <path key={p.id} d={p.d} fill="none" stroke={p.color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        ))}
        <line x1={cursorX} y1={0} x2={cursorX} y2={H} stroke="#fff" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}
