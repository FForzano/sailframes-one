import { useMemo } from "react";
import type { PolarPoint } from "@/types";

// Hand-rolled SVG polar diagram: boat speed (radius) vs true wind angle
// (0° = head to wind, at top), one curve per TWS bucket. Recharts has no true
// radius-by-value polar, so this stays bespoke — the analysis signature chart.
const SIZE = 320;
const C = SIZE / 2;
const R = 140;
const RINGS = [0.25, 0.5, 0.75, 1];
const SPOKES = [0, 45, 90, 135, 180];

// Blue→red by TWS bucket order (cool = light air, warm = breeze).
const TWS_COLORS = ["#2f9be0", "#3fbf7f", "#e0b24a", "#e0654f", "#9b6fe0"];

function polar(twaDeg: number, radius: number, side: 1 | -1): [number, number] {
  const th = (twaDeg * Math.PI) / 180;
  return [C + side * radius * Math.sin(th), C - radius * Math.cos(th)];
}

export function PolarChart({ points }: { points: PolarPoint[] }) {
  const { groups, maxSpeed } = useMemo(() => {
    const byTws = new Map<number, PolarPoint[]>();
    let mx = 1;
    for (const p of points) {
      if (p.speed_kts > mx) mx = p.speed_kts;
      const g = byTws.get(p.tws_kts) ?? [];
      g.push(p);
      byTws.set(p.tws_kts, g);
    }
    const gs = [...byTws.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([tws, pts]) => ({ tws, pts: pts.slice().sort((a, b) => a.twa_deg - b.twa_deg) }));
    return { groups: gs, maxSpeed: mx };
  }, [points]);

  if (!points.length) return null;

  return (
    <div className="sf-polar">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} style={{ width: "100%", maxWidth: 380 }}>
        {RINGS.map((f) => (
          <circle key={f} cx={C} cy={C} r={R * f} fill="none" stroke="var(--sf-border)" />
        ))}
        {SPOKES.map((a) => {
          const [x1, y1] = polar(a, R, 1);
          const [x2, y2] = polar(a, R, -1);
          return (
            <g key={a}>
              <line x1={C} y1={C} x2={x1} y2={y1} stroke="var(--sf-border)" strokeDasharray="2 3" />
              <line x1={C} y1={C} x2={x2} y2={y2} stroke="var(--sf-border)" strokeDasharray="2 3" />
              <text x={x1} y={y1} className="sf-polar__lbl" dx={a === 0 ? 0 : 4} dy={a === 0 ? -4 : 0}>
                {a}°
              </text>
            </g>
          );
        })}
        {groups.map((g, i) => {
          const color = TWS_COLORS[i % TWS_COLORS.length];
          const line = (side: 1 | -1) =>
            g.pts
              .map((p, j) => {
                const [x, y] = polar(p.twa_deg, (p.speed_kts / maxSpeed) * R, side);
                return `${j === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
              })
              .join(" ");
          return (
            <g key={g.tws}>
              <path d={line(1)} fill="none" stroke={color} strokeWidth={2} />
              <path d={line(-1)} fill="none" stroke={color} strokeWidth={2} opacity={0.5} />
            </g>
          );
        })}
      </svg>
      <div className="sf-polar__legend">
        {groups.map((g, i) => (
          <span key={g.tws}>
            <i style={{ background: TWS_COLORS[i % TWS_COLORS.length] }} />
            {g.tws.toFixed(0)} kn TWS
          </span>
        ))}
        <span className="sf-muted">0–{maxSpeed.toFixed(1)} kn</span>
      </div>
    </div>
  );
}
