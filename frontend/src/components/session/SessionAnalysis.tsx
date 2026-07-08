import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { sessionsService, sessionKeys } from "@/services/sessions";
import { polarsService, polarKeys } from "@/services/polars";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { fmtDuration, fmtDistanceNm, fmtKnots, fmtSeconds } from "@/utils/format";
import { PolarChart } from "./PolarChart";
import { legSequence } from "@/utils/legSequence";
import type { SessionLeg, SessionManeuver, UUID } from "@/types";

/** Rich per-session analysis (maneuvers, polar, VMG, …), assembled from its
 * normalized DB homes. 404 until the processing pipeline has run. */
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
            <PolarChart points={polar.data} targetPoints={a.polar_target} />
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
              <td>{fmtKnots(m.speed_loss_kts)}</td>
              <td>{fmtSeconds(m.recovery_time_sec)}</td>
              <td>{fmtSeconds(m.duration_sec)}</td>
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
  const seq = legSequence(legs);
  const ranked = legs.slice().sort((x, y) => y.avg_vmg_kts - x.avg_vmg_kts);
  return (
    <div className="sf-tablewrap">
      <table className="sf-table">
        <thead>
          <tr>
            <th>#</th>
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
              <td>{seq.get(l.id)}</td>
              <td>{t(`sessions.${l.leg_type}`)}</td>
              <td>{fmtKnots(l.avg_vmg_kts)}</td>
              <td>{fmtKnots(l.avg_speed_kts)}</td>
              <td>{fmtKnots(l.max_speed_kts)}</td>
              <td>{fmtDistanceNm(l.distance_nm)}</td>
              <td>{fmtDuration(l.duration_sec)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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

