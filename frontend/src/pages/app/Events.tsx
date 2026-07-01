import { useState } from "react";
import { useTranslation } from "react-i18next";
import { racesService } from "@/services/races.service";
import { eventsService, type RegattaCreate } from "@/services/events.service";
import { useResource } from "@/hooks/useResource";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { fmtDateRange } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { InputField } from "@/components/ui/InputField";
import type { Regatta } from "@/types";

// Events management. Writes are admin-gated server-side (see events.service);
// non-admins reaching here via the capability guard will get 403s surfaced as
// toasts. Advanced race editing (marks/course/start line) belongs to the race
// dashboard editor (M4) — this covers create/delete of the event hierarchy.
export function Events() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(() => racesService.listRegattas(), []);
  const [creating, setCreating] = useState(false);

  const onDelete = async (r: Regatta) => {
    if (!window.confirm(t("events.confirmDeleteRegatta"))) return;
    try {
      await eventsService.deleteRegatta(r.regatta_id);
      notify(t("events.deleted"), "success");
      reload();
    } catch (e) {
      notify(e instanceof ApiError ? e.detail : t("auth.genericError"), "error");
    }
  };

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("nav.events")}</h1>
        <Button onClick={() => setCreating(true)}>{t("events.newRegatta")}</Button>
      </div>

      <div className="sf-list">
        {(data ?? []).map((r) => (
          <RegattaRow key={r.regatta_id} regatta={r} onDelete={() => onDelete(r)} />
        ))}
      </div>

      {creating && (
        <RegattaModal
          onClose={() => setCreating(false)}
          onDone={() => {
            notify(t("events.created"), "success");
            setCreating(false);
            reload();
          }}
        />
      )}
    </div>
  );
}

function RegattaRow({ regatta, onDelete }: { regatta: Regatta; onDelete: () => void }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="sf-card">
      <div className="sf-toolbar">
        <div>
          <div className="sf-card__name">{regatta.name}</div>
          <div className="sf-muted">
            {[regatta.venue, fmtDateRange(regatta.start_date, regatta.end_date)].filter(Boolean).join(" · ")}
          </div>
        </div>
        <Button variant="ghost" onClick={() => setOpen((o) => !o)}>
          {open ? t("events.hide") : t("events.manage")}
        </Button>
        <Button variant="danger" onClick={onDelete}>
          {t("mysessions.delete")}
        </Button>
      </div>
      {open && <RegattaManage regatta={regatta} />}
    </div>
  );
}

function RegattaManage({ regatta }: { regatta: Regatta }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const { data, loading, reload } = useResource(
    () =>
      Promise.all([
        eventsService.listRacedays(regatta.regatta_id),
        racesService.listRaces({ regatta_id: regatta.regatta_id }),
      ]).then(([racedays, races]) => ({ racedays, races })),
    [regatta.regatta_id],
  );
  const [dayDate, setDayDate] = useState("");

  const addDay = async () => {
    if (!dayDate) return;
    try {
      await eventsService.createRaceday({ date: dayDate, regatta_id: regatta.regatta_id });
      notify(t("events.dayCreated"), "success");
      setDayDate("");
      reload();
    } catch (e) {
      notify(e instanceof ApiError ? e.detail : t("auth.genericError"), "error");
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="sf-mt">
      <h3 className="sf-section-title">{t("events.racedays")}</h3>
      <div className="sf-crew__row">
        <input className="sf-field__input" type="date" value={dayDate} onChange={(e) => setDayDate(e.target.value)} />
        <Button variant="ghost" onClick={addDay}>+ {t("events.addDay")}</Button>
      </div>
      <ul className="sf-plainlist">
        {(data?.racedays ?? []).map((d) => (
          <li key={d.raceday_id}>{d.date}{d.name ? ` · ${d.name}` : ""}</li>
        ))}
      </ul>

      <h3 className="sf-section-title">{t("events.races")}</h3>
      <RaceCreator regattaId={regatta.regatta_id} onDone={reload} />
      <ul className="sf-plainlist">
        {(data?.races ?? []).map((r) => (
          <li key={r.race_id}>{r.name || "Race"}{r.date ? ` · ${r.date}` : ""}</li>
        ))}
      </ul>
    </div>
  );
}

function RaceCreator({ regattaId, onDone }: { regattaId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !date) return;
    setBusy(true);
    try {
      // Default a 2-hour window at local noon; refine in the race editor later.
      await eventsService.createRace({
        name,
        date,
        start_time: `${date}T12:00:00Z`,
        end_time: `${date}T14:00:00Z`,
        regatta_id: regattaId,
      });
      notify(t("events.raceCreated"), "success");
      setName("");
      setDate("");
      onDone();
    } catch (e2) {
      notify(e2 instanceof ApiError ? e2.detail : t("auth.genericError"), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="sf-crew__row" onSubmit={submit}>
      <input className="sf-field__input" placeholder={t("events.raceName")} value={name} onChange={(e) => setName(e.target.value)} />
      <input className="sf-field__input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      <Button type="submit" variant="ghost" disabled={busy}>+ {t("events.addRace")}</Button>
    </form>
  );
}

function RegattaModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation();
  const [f, setF] = useState<RegattaCreate>({ name: "", venue: "", boat_class: "", start_date: "", end_date: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof RegattaCreate) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await eventsService.createRegatta(f);
      onDone();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  return (
    <Modal title={t("events.newRegatta")} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        <InputField id="reg-name" label={t("clubs.name")} value={f.name} onChange={set("name")} required />
        <InputField id="reg-venue" label={t("events.venue")} value={f.venue} onChange={set("venue")} required />
        <InputField id="reg-class" label={t("events.boatClass")} value={f.boat_class} onChange={set("boat_class")} required />
        <InputField id="reg-start" label={t("events.startDate")} type="date" value={f.start_date} onChange={set("start_date")} required />
        <InputField id="reg-end" label={t("events.endDate")} type="date" value={f.end_date} onChange={set("end_date")} required />
        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy}>
          {busy ? t("auth.pleaseWait") : t("events.newRegatta")}
        </Button>
      </form>
    </Modal>
  );
}
