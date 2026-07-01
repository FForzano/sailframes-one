import { useTranslation } from "react-i18next";
import { fleetService, FLEET_BOATS } from "@/services/fleet.service";
import { useResource } from "@/hooks/useResource";
import { ApiError } from "@/utils/api";
import { Spinner } from "@/components/ui/Spinner";

// boot.log battery lines (see CLAUDE.md boot.log format):
//   session t=<iso> batt=<v>V <pct>%
//   alive   t=<iso> batt=<v>V <pct>% heap=<n>
interface BattPoint {
  t: string;
  v: number;
  pct: number;
}
interface BoatBattery {
  boat: string;
  points: BattPoint[];
  error: string | null;
}

const LINE_RE = /t=(\S+)\s+batt=([\d.]+)V\s+(\d+)%/;

function parseBootlog(text: string): BattPoint[] {
  const points: BattPoint[] = [];
  for (const line of text.split("\n")) {
    const m = LINE_RE.exec(line);
    if (m) points.push({ t: m[1], v: parseFloat(m[2]), pct: parseInt(m[3], 10) });
  }
  return points;
}

async function loadAll(): Promise<BoatBattery[]> {
  return Promise.all(
    FLEET_BOATS.map(async (boat): Promise<BoatBattery> => {
      try {
        const text = await fleetService.getBootlog(boat);
        return { boat, points: parseBootlog(text), error: null };
      } catch (e) {
        const err =
          e instanceof ApiError && e.status === 404
            ? "no boot.log"
            : e instanceof ApiError
              ? e.detail
              : String(e);
        return { boat, points: [], error: err };
      }
    }),
  );
}

export function Battery() {
  const { t } = useTranslation();
  const { data, loading, error, reload } = useResource(loadAll, []);

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("battery.title")}</h1>
        <button className="sf-btn sf-btn--ghost" onClick={reload} disabled={loading}>
          {t("fleet.refresh")}
        </button>
      </div>
      <p className="sf-muted">{t("battery.subtitle")}</p>

      <div className="sf-cardgrid">
        {(data ?? []).map((b) => (
          <BatteryCard key={b.boat} boat={b} t={t} />
        ))}
      </div>
    </div>
  );
}

function BatteryCard({
  boat,
  t,
}: {
  boat: BoatBattery;
  t: (k: string) => string;
}) {
  const last = boat.points.at(-1);
  return (
    <section className="sf-card">
      <div className="sf-card__name">{boat.boat}</div>
      {boat.error ? (
        <p className="sf-muted">{boat.error}</p>
      ) : last ? (
        <>
          <div className={`sf-batt__pct ${last.pct < 15 ? "sf-danger-text" : last.pct < 30 ? "sf-warning-text" : ""}`}>
            {last.pct}% · {last.v.toFixed(2)} V
          </div>
          <Sparkline points={boat.points} />
          <p className="sf-muted">
            {t("battery.samples")}: {boat.points.length}
          </p>
        </>
      ) : (
        <p className="sf-muted">{t("battery.noData")}</p>
      )}
    </section>
  );
}

// Dependency-free inline SVG trend of battery % over the log window.
function Sparkline({ points }: { points: BattPoint[] }) {
  if (points.length < 2) return null;
  const W = 240;
  const H = 48;
  const n = points.length;
  const path = points
    .map((p, i) => {
      const x = (i / (n - 1)) * W;
      const y = H - (Math.max(0, Math.min(100, p.pct)) / 100) * H;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="sf-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H}>
      <path d={path} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
