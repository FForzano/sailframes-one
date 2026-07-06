import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { sessionsService, sessionKeys } from "@/services/sessions";
import { polarsService, polarKeys } from "@/services/polars";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { fmtDuration } from "@/utils/format";
import { PolarChart } from "./PolarChart";
import type { CorrelationMatrix, SensorStats, SessionLeg, SessionManeuver, UUID } from "@/types";

/** Rich per-session analysis (maneuvers, polar, VMG, correlations, …), assembled
 * from its normalized DB homes. 404 until the processing pipeline has run. */
export function SessionAnalysis({ sessionId }: { sessionId: UUID }) {
  const { t } = useTranslation();
  const analysis = useQuery({
    queryKey: sessionKeys.analysis(sessionId),
    queryFn: () => sessionsService.analysis(sessionId),
    retry: false, // 404 = not computed yet
  });
  const polar = useQuery({
    queryKey: polarKeys.session(sessionId),
    queryFn: () => polarsService.forSession(sessionId),
  });

  if (analysis.isLoading) return <Card title={t("sessions.analysis")}><Spinner /></Card>;
  if (!analysis.data) return null; // no analysis yet — hide the section entirely
  const a = analysis.data;

  return (
    <Card title={t("sessions.analysis")}>
      <div className="sf-section__body">
        {a.maneuver_summary && <ManeuverSummary summary={a.maneuver_summary} />}
        {!!polar.data?.length && (
          <Section title={t("sessions.polar")}>
            <PolarChart points={polar.data} />
          </Section>
        )}
        {!!a.vmg_series?.length && (
          <Section title={t("sessions.vmg")}>
            <VmgChart series={a.vmg_series} />
          </Section>
        )}
        {!!a.legs.length && (
          <Section title={t("sessions.legs")}>
            <LegsTable legs={a.legs} />
          </Section>
        )}
        {!!a.maneuvers.length && (
          <Section title={t("sessions.maneuvers")}>
            <ManeuversTable maneuvers={a.maneuvers} />
          </Section>
        )}
        {a.violin && (
          <Section title={t("sessions.maneuverCompare")}>
            <ViolinBars violin={a.violin} />
          </Section>
        )}
        {a.correlations && (
          <Section title={t("sessions.correlations")}>
            <CorrelationHeatmap data={a.correlations} />
          </Section>
        )}
        {a.sensor_stats && (
          <Section title={t("sessions.distributions")}>
            <SensorStatsTable stats={a.sensor_stats} />
          </Section>
        )}
      </div>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="sf-analysis__block">
      <h4 className="sf-analysis__title">{title}</h4>
      {children}
    </div>
  );
}

// --- maneuvers -------------------------------------------------------------------------

function ManeuverSummary({ summary }: { summary: Record<string, unknown> }) {
  const { t } = useTranslation();
  const rows = ["tacks", "gybes"] as const;
  const cols: [string, string][] = [
    ["count", t("sessions.count")],
    ["avg_speed_loss_kts", t("sessions.avgSpeedLoss")],
    ["avg_recovery_sec", t("sessions.avgRecovery")],
    ["avg_duration_sec", t("sessions.avgDuration")],
  ];
  return (
    <div className="sf-tablewrap">
      <table className="sf-table">
        <thead>
          <tr>
            <th />
            {cols.map(([, label]) => <th key={label}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const g = (summary[r] ?? {}) as Record<string, number>;
            return (
              <tr key={r}>
                <th>{t(`sessions.${r}`)}</th>
                {cols.map(([key]) => (
                  <td key={key}>{g[key] != null ? g[key] : "—"}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ManeuversTable({ maneuvers }: { maneuvers: SessionManeuver[] }) {
  const { t } = useTranslation();
  return (
    <div className="sf-tablewrap">
      <table className="sf-table">
        <thead>
          <tr>
            <th>{t("sessions.type")}</th>
            <th>{t("sessions.speedLoss")}</th>
            <th>{t("sessions.recovery")}</th>
            <th>{t("sessions.duration")}</th>
            <th>Δ°</th>
          </tr>
        </thead>
        <tbody>
          {maneuvers.map((m) => (
            <tr key={m.id}>
              <td>{t(`sessions.${m.maneuver_type}`)}</td>
              <td>{m.speed_loss_kts.toFixed(2)} kn</td>
              <td>{m.recovery_time_sec.toFixed(1)} s</td>
              <td>{m.duration_sec.toFixed(1)} s</td>
              <td>{Math.abs(m.heading_change_deg).toFixed(0)}°</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- legs ------------------------------------------------------------------------------

function LegsTable({ legs }: { legs: SessionLeg[] }) {
  const { t } = useTranslation();
  const ranked = legs.slice().sort((x, y) => y.avg_vmg_kts - x.avg_vmg_kts);
  return (
    <div className="sf-tablewrap">
      <table className="sf-table">
        <thead>
          <tr>
            <th>{t("sessions.type")}</th>
            <th>VMG</th>
            <th>{t("sessions.avgSpeed")}</th>
            <th>{t("sessions.maxSpeed")}</th>
            <th>{t("sessions.distance")}</th>
            <th>{t("sessions.duration")}</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((l) => (
            <tr key={l.id}>
              <td>{t(`sessions.${l.leg_type}`)}</td>
              <td>{l.avg_vmg_kts.toFixed(2)} kn</td>
              <td>{l.avg_speed_kts.toFixed(2)} kn</td>
              <td>{l.max_speed_kts.toFixed(2)} kn</td>
              <td>{l.distance_nm.toFixed(2)} nm</td>
              <td>{fmtDuration(l.duration_sec)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- VMG series ------------------------------------------------------------------------

function VmgChart({ series }: { series: { timestamp: number; vmg_kts: number }[] }) {
  const data = series.map((v) => ({ t: v.timestamp, vmg: v.vmg_kts }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--sf-border)" strokeDasharray="2 3" />
        <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} hide />
        <YAxis width={32} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => `${Number(v).toFixed(2)} kn`} labelFormatter={() => ""} />
        <Line type="monotone" dataKey="vmg" stroke="#2f9be0" strokeWidth={1.5}
          dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// --- maneuver comparison (violin → grouped means) --------------------------------------

const VIOLIN_METRICS: [string, string][] = [
  ["speed_loss_kts", "kn"],
  ["recovery_time_sec", "s"],
  ["duration_sec", "s"],
];

function ViolinBars({ violin }: { violin: Record<string, Record<string, { mean: number }>> }) {
  const { t } = useTranslation();
  const data = VIOLIN_METRICS.map(([metric]) => ({
    metric,
    tack: violin.tack?.[metric]?.mean ?? 0,
    gybe: violin.gybe?.[metric]?.mean ?? 0,
  }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--sf-border)" strokeDasharray="2 3" />
        <XAxis dataKey="metric" tick={{ fontSize: 11 }} />
        <YAxis width={32} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Bar dataKey="tack" name={t("sessions.tacks")} fill="#2f9be0" />
        <Bar dataKey="gybe" name={t("sessions.gybes")} fill="#e0654f" />
      </BarChart>
    </ResponsiveContainer>
  );
}

// --- correlations ----------------------------------------------------------------------

function corrColor(v: number): string {
  // Diverging: blue (+1) … neutral … red (−1).
  const a = Math.min(1, Math.abs(v));
  return v >= 0 ? `rgba(47,155,224,${a})` : `rgba(224,101,79,${a})`;
}

function CorrelationHeatmap({ data }: { data: CorrelationMatrix }) {
  const { variables, matrix } = data;
  return (
    <div className="sf-heatmap" style={{ gridTemplateColumns: `auto repeat(${variables.length}, 1fr)` }}>
      <div />
      {variables.map((v) => <div key={`h-${v}`} className="sf-heatmap__lbl">{v}</div>)}
      {variables.map((row) => (
        <Fragment key={`r-${row}`}>
          <div className="sf-heatmap__lbl">{row}</div>
          {variables.map((col) => {
            const val = matrix[row]?.[col] ?? 0;
            return (
              <div key={`${row}-${col}`} className="sf-heatmap__cell"
                style={{ background: corrColor(val) }}>
                {val.toFixed(2)}
              </div>
            );
          })}
        </Fragment>
      ))}
    </div>
  );
}

// --- sensor distributions --------------------------------------------------------------

const STAT_COLS = ["mean", "max", "std", "median"];

function SensorStatsTable({ stats }: { stats: SensorStats }) {
  return (
    <div className="sf-tablewrap">
      <table className="sf-table">
        <thead>
          <tr>
            <th />
            {STAT_COLS.map((c) => <th key={c}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.entries(stats).map(([variable, metrics]) => (
            <tr key={variable}>
              <th>{variable}</th>
              {STAT_COLS.map((c) => (
                <td key={c}>{metrics[c] != null ? metrics[c] : "—"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
