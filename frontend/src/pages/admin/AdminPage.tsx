import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { windService, windKeys } from "@/services/wind";
import { usersService, userKeys } from "@/services/users";
import { devicesService, deviceKeys } from "@/services/devices";
import { boatsService, boatKeys, type BoatClassSort, type SortOrder } from "@/services/boats";
import { useToast } from "@/hooks/useToast";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { InputField, TextAreaField } from "@/components/ui/InputField";
import { Modal } from "@/components/ui/Modal";
import { Spinner } from "@/components/ui/Spinner";
import { ImageUploader } from "@/components/common/ImageUploader";
import { fmtDateTime, userLabel } from "@/utils/format";
import type { BoatClass, HullType, RigType, SpinnakerType, UUID, WindStation } from "@/types";

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

function WindStations() {
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
      await queryClient.invalidateQueries({ queryKey: windKeys.stations });
    },
    onError: () => notify(t("errors.generic"), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: UUID) => windService.removeStation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: windKeys.stations }),
  });

  return (
    <Card title={t("admin.windStations")}>
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

      <form
        className="sf-form__row"
        style={{ alignItems: "end", marginTop: "0.75rem" }}
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
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
        <div className="sf-field">
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
    </Card>
  );
}

function Users() {
  const { t } = useTranslation();
  const users = useQuery({ queryKey: userKeys.all, queryFn: usersService.list });
  return (
    <Card title={t("admin.users")}>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("common.name")}</th>
              <th>{t("auth.email")}</th>
              <th>{t("common.status")}</th>
              <th>{t("admin.superadmin")}</th>
            </tr>
          </thead>
          <tbody>
            {users.data?.map((u) => (
              <tr key={u.id}>
                <td>{userLabel(u)}</td>
                <td className="sf-muted">{u.email}</td>
                <td>
                  <span
                    className={
                      u.status === "active" ? "sf-badge sf-badge--success" : "sf-badge sf-badge--danger"
                    }
                  >
                    {u.status}
                  </span>
                </td>
                <td>{u.is_superadmin ? "✓" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DeviceTypes() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", category: "boat_tracker", parser_key: "" });

  const types = useQuery({ queryKey: deviceKeys.types, queryFn: devicesService.listTypes });
  const create = useMutation({
    mutationFn: () => devicesService.createType(form),
    onSuccess: async () => {
      setForm({ name: "", category: "boat_tracker", parser_key: "" });
      await queryClient.invalidateQueries({ queryKey: deviceKeys.types });
    },
    onError: () => notify(t("errors.generic"), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: UUID) => devicesService.removeType(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: deviceKeys.types }),
    onError: () => notify(t("errors.generic"), "error"),
  });

  return (
    <Card title={t("admin.deviceTypes")}>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("common.name")}</th>
              <th>{t("admin.category")}</th>
              <th>{t("admin.parserKey")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {types.data?.map((dt) => (
              <tr key={dt.id}>
                <td>{dt.name}</td>
                <td>{dt.category}</td>
                <td className="sf-muted">{dt.parser_key}</td>
                <td>
                  <Button variant="danger" className="sf-btn--sm" onClick={() => remove.mutate(dt.id)}>
                    ×
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form
        className="sf-form__row"
        style={{ alignItems: "end", marginTop: "0.75rem" }}
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <InputField
          label={t("common.name")}
          id="dt-name"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          required
        />
        <Select
          label={t("admin.category")}
          id="dt-cat"
          value={form.category}
          onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
        >
          <option value="boat_tracker">boat_tracker</option>
          <option value="wearable">wearable</option>
          <option value="wind_station">wind_station</option>
        </Select>
        <InputField
          label={t("admin.parserKey")}
          id="dt-parser"
          value={form.parser_key}
          onChange={(e) => setForm((f) => ({ ...f, parser_key: e.target.value }))}
          placeholder="e1_csv_v1"
          required
        />
        <div className="sf-field">
          <Button type="submit" disabled={create.isPending || !form.name || !form.parser_key}>
            {t("common.add")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

const CLASS_PAGE_SIZE = 20;

const emptyClassForm = {
  name: "",
  description: "",
  loa_m: "",
  beam_m: "",
  sail_area_sqm: "",
  crew_size: "",
  hull_type: "",
  rig_type: "",
  spinnaker_type: "",
  py_rating: "",
  rya_class_id: "",
};

function BoatClasses() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [hullFilter, setHullFilter] = useState<HullType | "">("");
  const [sort, setSort] = useState<BoatClassSort>("name");
  const [order, setOrder] = useState<SortOrder>("asc");
  const [editing, setEditing] = useState<BoatClass | null>(null);
  const [form, setForm] = useState(emptyClassForm);

  const classes = useQuery({
    queryKey: boatKeys.classes(page, search, hullFilter, sort, order),
    queryFn: () =>
      boatsService.listClasses({
        limit: CLASS_PAGE_SIZE,
        offset: page * CLASS_PAGE_SIZE,
        search: search || undefined,
        hullType: hullFilter,
        sort,
        order,
      }),
  });

  useEffect(() => {
    if (editing) {
      setForm({
        name: editing.name ?? "",
        description: editing.description ?? "",
        loa_m: editing.loa_m?.toString() ?? "",
        beam_m: editing.beam_m?.toString() ?? "",
        sail_area_sqm: editing.sail_area_sqm?.toString() ?? "",
        crew_size: editing.crew_size?.toString() ?? "",
        hull_type: editing.hull_type ?? "",
        rig_type: editing.rig_type ?? "",
        spinnaker_type: editing.spinnaker_type ?? "",
        py_rating: editing.py_rating?.toString() ?? "",
        rya_class_id: editing.rya_class_id?.toString() ?? "",
      });
    }
  }, [editing]);

  // Keep the open edit modal's logo preview in sync after an upload
  // triggers a list refetch (the modal doesn't re-fetch its own copy).
  useEffect(() => {
    if (editing && classes.data) {
      const fresh = classes.data.find((c) => c.id === editing.id);
      if (fresh && fresh.logo !== editing.logo) setEditing(fresh);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classes.data]);

  // Prefix match invalidates every page ([boat-classes, page] for each page).
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["boat-classes"] });

  const create = useMutation({
    mutationFn: () => boatsService.createClass({ name }),
    onSuccess: async () => {
      setName("");
      await invalidate();
    },
    onError: () => notify(t("errors.generic"), "error"),
  });
  const save = useMutation({
    mutationFn: () =>
      boatsService.updateClass(editing!.id, {
        name: form.name,
        description: form.description || null,
        loa_m: form.loa_m ? Number(form.loa_m) : null,
        beam_m: form.beam_m ? Number(form.beam_m) : null,
        sail_area_sqm: form.sail_area_sqm ? Number(form.sail_area_sqm) : null,
        crew_size: form.crew_size ? Number(form.crew_size) : null,
        hull_type: (form.hull_type || null) as HullType | null,
        rig_type: (form.rig_type || null) as RigType | null,
        spinnaker_type: (form.spinnaker_type || null) as SpinnakerType | null,
        py_rating: form.py_rating ? Math.round(Number(form.py_rating)) : null,
        rya_class_id: form.rya_class_id ? Math.round(Number(form.rya_class_id)) : null,
      }),
    onSuccess: async () => {
      setEditing(null);
      notify(t("common.saved"), "success");
      await invalidate();
    },
    onError: () => notify(t("errors.generic"), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: UUID) => boatsService.removeClass(id),
    onSuccess: () => invalidate(),
    onError: () => notify(t("errors.generic"), "error"),
  });

  return (
    <Card title={t("admin.boatClasses")}>
      <div className="sf-form__row" style={{ alignItems: "end" }}>
        <InputField
          label={t("common.search")}
          id="bc-search"
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder={t("admin.boatClasses")}
        />
        <Select
          label={t("admin.hullType")}
          id="bc-hull-filter"
          value={hullFilter}
          onChange={(e) => {
            setHullFilter(e.target.value as HullType | "");
            setPage(0);
          }}
        >
          <option value="">{t("admin.allHullTypes")}</option>
          <option value="monohull">{t("admin.monohull")}</option>
          <option value="multihull">{t("admin.multihull")}</option>
        </Select>
        <Select
          label={t("common.sortBy")}
          id="bc-sort"
          value={sort}
          onChange={(e) => setSort(e.target.value as BoatClassSort)}
        >
          <option value="name">{t("common.name")}</option>
          <option value="py_rating">{t("admin.pyRating")}</option>
          <option value="crew_size">{t("admin.crewSize")}</option>
          <option value="rya_class_id">{t("admin.ryaClassId")}</option>
        </Select>
        <Select
          label={t("common.sortOrder")}
          id="bc-order"
          value={order}
          onChange={(e) => setOrder(e.target.value as SortOrder)}
        >
          <option value="asc">{t("common.ascending")}</option>
          <option value="desc">{t("common.descending")}</option>
        </Select>
      </div>
      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th />
              <th>{t("common.name")}</th>
              <th>{t("admin.hullType")}</th>
              <th>{t("admin.loa")}</th>
              <th>{t("admin.sailArea")}</th>
              <th>{t("admin.crewSize")}</th>
              <th>{t("admin.rigType")}</th>
              <th>{t("admin.spinnakerType")}</th>
              <th>{t("admin.pyRating")}</th>
              <th>{t("admin.ryaClassId")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {classes.data?.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.logo ? (
                    <img className="sf-avatar sf-avatar--sm" src={c.logo.url} alt="" />
                  ) : (
                    <span className="sf-muted">—</span>
                  )}
                </td>
                <td>
                  <strong>{c.name}</strong>
                </td>
                <td>{c.hull_type ? t(`admin.${c.hull_type}`) : "—"}</td>
                <td>{c.loa_m ?? "—"}</td>
                <td>{c.sail_area_sqm ?? "—"}</td>
                <td>{c.crew_size ?? "—"}</td>
                <td>{c.rig_type ? t(`admin.${c.rig_type}`) : "—"}</td>
                <td>{c.spinnaker_type ? t(`admin.spinnaker_${c.spinnaker_type}`) : "—"}</td>
                <td>{c.py_rating ?? "—"}</td>
                <td>{c.rya_class_id ?? "—"}</td>
                <td>
                  <span style={{ display: "flex", gap: "0.4rem" }}>
                    <Button
                      variant="ghost"
                      className="sf-btn--sm"
                      aria-label={t("common.edit")}
                      title={t("common.edit")}
                      onClick={() => setEditing(c)}
                    >
                      ✎
                    </Button>
                    <Button
                      variant="danger"
                      className="sf-btn--sm"
                      aria-label={t("common.delete")}
                      title={t("common.delete")}
                      onClick={() => remove.mutate(c.id)}
                    >
                      ×
                    </Button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
          disabled={(classes.data?.length ?? 0) < CLASS_PAGE_SIZE}
          onClick={() => setPage((p) => p + 1)}
        >
          ›
        </Button>
      </div>

      <form
        className="sf-form__row"
        style={{ alignItems: "end", marginTop: "0.75rem" }}
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <InputField
          label={t("common.name")}
          id="bc-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <div className="sf-field">
          <Button type="submit" disabled={create.isPending || !name}>
            {t("common.add")}
          </Button>
        </div>
      </form>

      {editing && (
        <Modal title={t("common.edit")} onClose={() => setEditing(null)}>
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
              {editing.logo ? (
                <img className="sf-avatar" src={editing.logo.url} alt="" />
              ) : (
                <span className="sf-avatar sf-avatar--initials">—</span>
              )}
              <ImageUploader
                crop
                create={() => boatsService.uploadClassLogo(editing.id)}
                confirm={(imageId) => boatsService.confirmClassLogo(editing.id, imageId)}
                onDone={invalidate}
              />
            </div>
            <InputField
              label={t("common.name")}
              id="bce-name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
            <TextAreaField
              label={t("common.description")}
              id="bce-desc"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
            <div className="sf-form__row">
              <InputField
                label={t("admin.loa")}
                id="bce-loa"
                type="number"
                step="any"
                value={form.loa_m}
                onChange={(e) => setForm((f) => ({ ...f, loa_m: e.target.value }))}
              />
              <InputField
                label={t("admin.beam")}
                id="bce-beam"
                type="number"
                step="any"
                value={form.beam_m}
                onChange={(e) => setForm((f) => ({ ...f, beam_m: e.target.value }))}
              />
              <InputField
                label={t("admin.sailArea")}
                id="bce-sail"
                type="number"
                step="any"
                value={form.sail_area_sqm}
                onChange={(e) => setForm((f) => ({ ...f, sail_area_sqm: e.target.value }))}
              />
            </div>
            <div className="sf-form__row">
              <InputField
                label={t("admin.crewSize")}
                id="bce-crew"
                type="number"
                step="1"
                value={form.crew_size}
                onChange={(e) => setForm((f) => ({ ...f, crew_size: e.target.value }))}
              />
              <Select
                label={t("admin.hullType")}
                id="bce-hull"
                value={form.hull_type}
                onChange={(e) => setForm((f) => ({ ...f, hull_type: e.target.value }))}
              >
                <option value="">—</option>
                <option value="monohull">{t("admin.monohull")}</option>
                <option value="multihull">{t("admin.multihull")}</option>
              </Select>
              <Select
                label={t("admin.rigType")}
                id="bce-rig"
                value={form.rig_type}
                onChange={(e) => setForm((f) => ({ ...f, rig_type: e.target.value }))}
              >
                <option value="">—</option>
                <option value="sloop">{t("admin.sloop")}</option>
                <option value="una">{t("admin.una")}</option>
              </Select>
            </div>
            <div className="sf-form__row">
              <Select
                label={t("admin.spinnakerType")}
                id="bce-spinnaker"
                value={form.spinnaker_type}
                onChange={(e) => setForm((f) => ({ ...f, spinnaker_type: e.target.value }))}
              >
                <option value="">—</option>
                <option value="none">{t("admin.spinnaker_none")}</option>
                <option value="asymmetric">{t("admin.spinnaker_asymmetric")}</option>
                <option value="symmetric">{t("admin.spinnaker_symmetric")}</option>
              </Select>
              <InputField
                label={t("admin.pyRating")}
                id="bce-py"
                type="number"
                step="1"
                value={form.py_rating}
                onChange={(e) => setForm((f) => ({ ...f, py_rating: e.target.value }))}
              />
              <InputField
                label={t("admin.ryaClassId")}
                id="bce-rya"
                type="number"
                step="1"
                value={form.rya_class_id}
                onChange={(e) => setForm((f) => ({ ...f, rya_class_id: e.target.value }))}
              />
            </div>
            <div className="sf-form__actions">
              <Button type="submit" disabled={save.isPending}>
                {t("common.save")}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </Card>
  );
}

export function AdminPage() {
  const { t } = useTranslation();
  return (
    <div className="sf-section">
      <h1>{t("admin.title")}</h1>
      <div className="sf-section__body">
        <WindStations />
        <Users />
        <DeviceTypes />
        <BoatClasses />
      </div>
    </div>
  );
}
