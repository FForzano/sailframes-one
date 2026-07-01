import { useState } from "react";
import { useTranslation } from "react-i18next";
import { fleetService } from "@/services/fleet.service";
import { useResource } from "@/hooks/useResource";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import type { FleetRow } from "@/types";

// Fleet health table — one row per boat from its raw/<boat>/_health.json
// snapshot. Anonymous-friendly (proxied read); a boat with no snapshot shows a
// muted "no snapshot" row rather than breaking the table.
export function FleetStatus() {
  const { t } = useTranslation();
  const { data, loading, error, reload } = useResource(() => fleetService.loadAll(), []);
  const [filter, setFilter] = useState("");

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  const rows = (data ?? []).filter((r) => matches(r, filter));

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("fleet.title")}</h1>
        <input
          className="sf-field__input"
          type="search"
          placeholder={t("fleet.filterPlaceholder")}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <Button variant="ghost" onClick={reload} disabled={loading}>
          {t("fleet.refresh")}
        </Button>
      </div>

      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("fleet.boat")}</th>
              <th>{t("fleet.battery")}</th>
              <th>{t("fleet.fix")}</th>
              <th>{t("fleet.fw")}</th>
              <th>{t("fleet.role")}</th>
              <th>{t("fleet.state")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <FleetTableRow key={r.boat} row={r} t={t} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FleetTableRow({
  row,
  t,
}: {
  row: FleetRow;
  t: (k: string) => string;
}) {
  if (!row.health) {
    return (
      <tr className="sf-table__muted">
        <td>{row.boat}</td>
        <td colSpan={5}>{row.error ?? t("fleet.noSnapshot")}</td>
      </tr>
    );
  }
  const h = row.health;
  const batt =
    h.battery_pct != null
      ? `${h.battery_pct}%${h.battery_v != null ? ` (${h.battery_v} V)` : ""}`
      : "—";
  const fix =
    h.fix_quality != null
      ? `q${h.fix_quality}${h.sat_count != null ? ` · ${h.sat_count} sat` : ""}`
      : "—";
  return (
    <tr>
      <td>{h.boat_id ?? row.boat}</td>
      <td className={battClass(h.battery_pct)}>{batt}</td>
      <td>{fix}</td>
      <td>{h.fw ?? "—"}</td>
      <td>{h.unit_role ?? "—"}</td>
      <td>{h.logging ? t("fleet.recording") : t("fleet.idle")}</td>
    </tr>
  );
}

function battClass(pct?: number): string {
  if (pct == null) return "";
  if (pct < 15) return "sf-danger-text";
  if (pct < 30) return "sf-warning-text";
  return "";
}

function matches(r: FleetRow, filter: string): boolean {
  const q = filter.trim().toLowerCase();
  if (!q) return true;
  const hay = [
    r.boat,
    r.health?.boat_id,
    r.health?.fw,
    r.health?.unit_role,
    r.health?.logging ? "recording" : "idle",
    r.health && r.health.battery_pct != null && r.health.battery_pct < 20 ? "low battery" : "",
    r.health && !r.health.fix_quality ? "no fix" : "",
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}
