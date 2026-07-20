import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { windService, windKeys } from "@/services/wind";
import { useToast } from "@/hooks/useToast";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { InputField } from "@/components/ui/InputField";
import { Modal } from "@/components/ui/Modal";
import { Spinner } from "@/components/ui/Spinner";
import { fmtDateTime } from "@/utils/format";
import type { UUID, WindStation } from "@/types";

const PROVIDERS = [
  "noaa_ndbc",
  "noaa_metar",
  "custom_device",
  "cumulus_realtime",
  "cumulus_gauges_json",
];
const STATION_TYPES = ["buoy", "metar", "custom_device"];
// Providers polled by URL (source_url) rather than looked up by
// external_station_id against a fixed provider API — see
// backend/services/wind_providers/__init__.py::URL_BASED_PROVIDERS.
const URL_BASED_PROVIDERS = ["cumulus_realtime", "cumulus_gauges_json"];

export function WindStationsPage() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    provider: "noaa_ndbc",
    external_station_id: "",
    source_url: "",
    name: "",
    station_type: "buoy",
    lat: "",
    lng: "",
  });
  const isUrlBased = URL_BASED_PROVIDERS.includes(form.provider);
  const [observing, setObserving] = useState<WindStation | null>(null);
  const [page, setPage] = useState(0);
  const [adding, setAdding] = useState(false);
  const OBS_PAGE_SIZE = 50;

  const stations = useQuery({ queryKey: windKeys.stations, queryFn: windService.listStations });
  const observations = useQuery({
    // The cache grows without bound (every scheduler tick upserts more rows),
    // so the admin view pages through it server-side rather than fetching
    // everything and slicing client-side.
    queryKey: windKeys.observations(observing?.id ?? "none", String(page)),
    queryFn: () =>
      windService.observations(observing!.id, { limit: OBS_PAGE_SIZE, offset: page * OBS_PAGE_SIZE }),
    enabled: observing !== null,
  });

  const create = useMutation({
    mutationFn: () =>
      windService.createStation({
        provider: form.provider,
        external_station_id: form.external_station_id,
        source_url: form.source_url || undefined,
        name: form.name || undefined,
        station_type: form.station_type,
        lat: form.lat ? Number(form.lat) : undefined,
        lng: form.lng ? Number(form.lng) : undefined,
      }),
    onSuccess: async () => {
      setForm({
        provider: "noaa_ndbc",
        external_station_id: "",
        source_url: "",
        name: "",
        station_type: "buoy",
        lat: "",
        lng: "",
      });
      setAdding(false);
      await queryClient.invalidateQueries({ queryKey: windKeys.stations });
    },
    onError: () => notify(t("errors.generic"), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: UUID) => windService.removeStation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: windKeys.stations }),
  });

  return (
    <>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("admin.provider")}</th>
              <th>{t("admin.stationId")}</th>
              <th>{t("admin.sourceUrl")}</th>
              <th>{t("common.name")}</th>
              <th>{t("admin.stationType")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {stations.data?.map((s) => (
              <tr key={s.id}>
                <td>{s.provider}</td>
                <td>{s.external_station_id}</td>
                <td>
                  {s.source_url ? (
                    <a href={s.source_url} target="_blank" rel="noreferrer">
                      {s.source_url}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
                <td>{s.name ?? "—"}</td>
                <td>{s.station_type}</td>
                <td style={{ display: "flex", gap: "0.4rem" }}>
                  <Button
                    variant="ghost"
                    className="sf-btn--sm"
                    onClick={() => {
                      setObserving(observing?.id === s.id ? null : s);
                      setPage(0);
                    }}
                  >
                    {t("admin.observations")}
                  </Button>
                  <Button
                    variant="danger"
                    className="sf-btn--sm"
                    onClick={() => remove.mutate(s.id)}
                  >
                    ×
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {observing && (
        <div style={{ marginTop: "0.75rem" }}>
          <h3>
            {t("admin.lastObservations")} — {observing.external_station_id}
          </h3>
          {observations.isLoading ? (
            <Spinner />
          ) : (
            <div className="sf-tablewrap" style={{ maxHeight: 260, overflowY: "auto" }}>
              <table className="sf-table">
                <thead>
                  <tr>
                    <th>{t("common.date")}</th>
                    <th>TWD</th>
                    <th>TWS</th>
                    <th>Gust</th>
                  </tr>
                </thead>
                <tbody>
                  {(observations.data ?? []).map((o) => (
                    <tr key={o.observed_at}>
                      <td>{fmtDateTime(o.observed_at)}</td>
                      <td>{o.twd_deg != null ? `${o.twd_deg}°` : "—"}</td>
                      <td>{o.tws_kts != null ? `${o.tws_kts} kn` : "—"}</td>
                      <td>{o.gust_kts != null ? `${o.gust_kts} kn` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="sf-form__actions" style={{ justifyContent: "flex-start" }}>
            <Button
              variant="ghost"
              className="sf-btn--sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ‹
            </Button>
            <Button
              variant="ghost"
              className="sf-btn--sm"
              disabled={(observations.data?.length ?? 0) < OBS_PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              ›
            </Button>
          </div>
        </div>
      )}

      <div className="sf-form__actions" style={{ justifyContent: "flex-start", marginTop: "0.75rem" }}>
        <Button onClick={() => setAdding(true)}>{t("admin.addStation")}</Button>
      </div>

      {adding && (
        <Modal title={t("admin.addStation")} onClose={() => setAdding(false)}>
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <div className="sf-form__row">
              <Select
                label={t("admin.provider")}
                id="ws-provider"
                value={form.provider}
                onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
              <InputField
                label={t("admin.stationId")}
                id="ws-ext"
                value={form.external_station_id}
                onChange={(e) => setForm((f) => ({ ...f, external_station_id: e.target.value }))}
                placeholder="44013"
                required
              />
            </div>
            {isUrlBased && (
              <InputField
                label={t("admin.sourceUrl")}
                id="ws-source-url"
                value={form.source_url}
                onChange={(e) => setForm((f) => ({ ...f, source_url: e.target.value }))}
                placeholder="https://example.com/realtime.txt"
                required
              />
            )}
            <div className="sf-form__row">
              <InputField
                label="Lat"
                id="ws-lat"
                type="number"
                step="any"
                value={form.lat}
                onChange={(e) => setForm((f) => ({ ...f, lat: e.target.value }))}
                placeholder="44.79"
              />
              <InputField
                label="Lng"
                id="ws-lng"
                type="number"
                step="any"
                value={form.lng}
                onChange={(e) => setForm((f) => ({ ...f, lng: e.target.value }))}
                placeholder="12.33"
              />
            </div>
            <div className="sf-form__row">
              <InputField
                label={t("common.name")}
                id="ws-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
              <Select
                label={t("admin.stationType")}
                id="ws-type"
                value={form.station_type}
                onChange={(e) => setForm((f) => ({ ...f, station_type: e.target.value }))}
              >
                {STATION_TYPES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
            </div>
            <div className="sf-form__actions">
              <Button
                type="submit"
                disabled={
                  create.isPending ||
                  !form.external_station_id ||
                  (isUrlBased && !form.source_url)
                }
              >
                {t("admin.addStation")}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
