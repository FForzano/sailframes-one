import { useState } from "react";
import { useTranslation } from "react-i18next";
import { sessionsService, type CrewSlot } from "@/services/sessions.service";
import { useResource } from "@/hooks/useResource";
import { useCapabilities } from "@/hooks/useCapabilities";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { fmtDuration, fmtShortDate } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { SessionSummary, Visibility } from "@/types";

const VIS: Visibility[] = ["private", "group", "club", "public"];

// Personal sessions view. The list is the server's visibility-filtered set
// (own/crewed/club/group + public); editing crew/visibility and deleting are
// gated by the server — the client only hides the delete button without
// session.delete to avoid dead-ends.
export function MySessions() {
  const { t } = useTranslation();
  const caps = useCapabilities();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(() => sessionsService.list(), []);
  const [editing, setEditing] = useState<SessionSummary | null>(null);

  const canDelete = caps.isSuperadmin || caps.can("session.delete");

  const onDelete = async (s: SessionSummary) => {
    if (!window.confirm(t("mysessions.confirmDelete"))) return;
    try {
      await sessionsService.remove(s.device_id, s.date);
      notify(t("mysessions.deleted"), "success");
      reload();
    } catch (e) {
      notify(e instanceof ApiError ? e.detail : t("auth.genericError"), "error");
    }
  };

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("nav.mySessions")}</h1>
      <div className="sf-list">
        {(data ?? []).map((s) => (
          <div key={`${s.device_id}/${s.date}`} className="sf-listrow">
            <span className="sf-listrow__meta">{fmtShortDate(s.date)}</span>
            <span className="sf-listrow__main">
              {s.name || s.boat || s.device_id}
              <span className="sf-chip sf-chip--sm">{s.visibility ?? "public"}</span>
            </span>
            <span className="sf-listrow__meta">{fmtDuration(s.duration_sec)}</span>
            <Button variant="ghost" onClick={() => setEditing(s)}>
              {t("mysessions.edit")}
            </Button>
            {canDelete && (
              <Button variant="danger" onClick={() => onDelete(s)}>
                {t("mysessions.delete")}
              </Button>
            )}
          </div>
        ))}
      </div>

      {editing && (
        <EditSessionModal
          session={editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            notify(t("mysessions.saved"), "success");
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function EditSessionModal({
  session,
  onClose,
  onDone,
}: {
  session: SessionSummary;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [visibility, setVisibility] = useState<Visibility>(session.visibility ?? "public");
  const [crew, setCrew] = useState<CrewSlot[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const addSlot = () => setCrew((c) => [...c, { guest_name: "", boat_role: "crew" }]);
  const setSlot = (i: number, patch: Partial<CrewSlot>) =>
    setCrew((c) => c.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const rmSlot = (i: number) => setCrew((c) => c.filter((_, j) => j !== i));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      // Only guest slots with a name are sent; empties are dropped.
      const cleaned = crew
        .filter((s) => (s.guest_name ?? "").trim())
        .map((s) => ({ guest_name: s.guest_name!.trim(), boat_role: s.boat_role || null }));
      await sessionsService.editCrew(session.device_id, session.date, {
        crew: cleaned,
        visibility,
      });
      onDone();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  return (
    <Modal title={t("mysessions.edit")} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        <Select id="sess-vis" label={t("sessions.visibility")} value={visibility} onChange={(e) => setVisibility(e.target.value as Visibility)}>
          {VIS.map((v) => (
            <option key={v} value={v}>{v}</option>
          ))}
        </Select>

        <div className="sf-crew">
          <span className="sf-field__label">{t("mysessions.crew")}</span>
          {crew.map((s, i) => (
            <div key={i} className="sf-crew__row">
              <input
                className="sf-field__input"
                placeholder={t("mysessions.guestName")}
                value={s.guest_name ?? ""}
                onChange={(e) => setSlot(i, { guest_name: e.target.value })}
              />
              <input
                className="sf-field__input"
                placeholder={t("mysessions.role")}
                value={s.boat_role ?? ""}
                onChange={(e) => setSlot(i, { boat_role: e.target.value })}
              />
              <button type="button" className="sf-btn sf-btn--ghost" onClick={() => rmSlot(i)}>×</button>
            </div>
          ))}
          <button type="button" className="sf-btn sf-btn--ghost" onClick={addSlot}>
            + {t("mysessions.addCrew")}
          </button>
        </div>

        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy}>
          {busy ? t("auth.pleaseWait") : t("boats.save")}
        </Button>
      </form>
    </Modal>
  );
}
