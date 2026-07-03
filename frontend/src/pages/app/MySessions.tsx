import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { sessionsService, type CrewSlot } from "@/services/sessions.service";
import { boatsService } from "@/services/boats.service";
import { devicesService } from "@/services/devices.service";
import { useResource } from "@/hooks/useResource";
import { useCapabilities } from "@/hooks/useCapabilities";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { fmtDuration, fmtShortDate } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { Boat, BoatMember, Device, SessionSummary, Visibility } from "@/types";

const VIS: Visibility[] = ["private", "group", "club", "public"];

// Personal sessions view. The list is the server's visibility-filtered set
// (own/crewed/club/group + public); editing crew/visibility and deleting are
// gated by the server — the client only hides the delete button without
// session.delete to avoid dead-ends.
export function MySessions() {
  const { t } = useTranslation();
  const caps = useCapabilities();
  const { caps: authCaps } = useAuth();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(() => sessionsService.list(), []);
  const [editing, setEditing] = useState<SessionSummary | null>(null);
  const [creating, setCreating] = useState(false);

  const canDelete = caps.isSuperadmin || caps.can("session.delete");

  // Manual sessions still processing their GPX upload — poll the list so
  // rows flip from "processing" to "ready" without a manual refresh.
  const hasProcessing = (data ?? []).some(
    (s) => s.source === "manual" && (s.processing_status === "pending" || s.processing_status === "processing"),
  );
  useEffect(() => {
    if (!hasProcessing) return;
    const timer = setInterval(reload, 5000);
    return () => clearInterval(timer);
  }, [hasProcessing, reload]);

  const onDelete = async (s: SessionSummary) => {
    if (!window.confirm(t("mysessions.confirmDelete"))) return;
    try {
      await sessionsService.remove(s.device_id!, s.date);
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
      <div className="sf-page__head">
        <h1 className="sf-page__title">{t("nav.mySessions")}</h1>
        <Button onClick={() => setCreating(true)}>{t("mysessions.create")}</Button>
      </div>
      <div className="sf-list">
        {(data ?? []).map((s) => (
          <div key={s.id} className="sf-listrow">
            <span className="sf-listrow__meta">{fmtShortDate(s.date)}</span>
            <span className="sf-listrow__main">
              {s.name || s.boat || s.device_id}
              <span className="sf-chip sf-chip--sm">{s.visibility ?? "public"}</span>
              {s.source === "manual" && s.processing_status !== "ready" && (
                <span className="sf-chip sf-chip--sm">
                  {s.processing_status === "failed"
                    ? t("mysessions.statusFailed")
                    : t("mysessions.statusProcessing")}
                </span>
              )}
            </span>
            <span className="sf-listrow__meta">{fmtDuration(s.duration_sec)}</span>
            {s.source === "device" && (
              <Button variant="ghost" onClick={() => setEditing(s)}>
                {t("mysessions.edit")}
              </Button>
            )}
            {canDelete && s.source === "device" && (
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

      {creating && authCaps && (
        <CreateSessionModal
          userId={authCaps.user.id}
          onClose={() => setCreating(false)}
          onDone={() => {
            notify(t("mysessions.created"), "success");
            setCreating(false);
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
      await sessionsService.editCrew(session.device_id!, session.date, {
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

// Create a sailing outing: boat + crew (registered members from the boat's
// roster, or free-text guests) + an optional device. Devices are just a
// convenience for automatic acquisition — picking one claims/edits that
// device's already-uploaded session for the date; leaving it out creates a
// device-less "manual" session, which then needs a GPX track uploaded (S3
// signed-URL-style: an endpoint hands back a URL, we PUT the file there).
function CreateSessionModal({
  userId,
  onClose,
  onDone,
}: {
  userId: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { data: boats } = useResource(() => boatsService.list(), []);
  const myBoats = (boats ?? []).filter((b) => b.members.some((m) => m.user_id === userId));

  const [boatId, setBoatId] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [deviceId, setDeviceId] = useState("");
  const [devices, setDevices] = useState<Device[]>([]);
  const [boatMembers, setBoatMembers] = useState<BoatMember[]>([]);
  const [crew, setCrew] = useState<CrewSlot[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [step, setStep] = useState<"form" | "upload">("form");
  const [createdSessionId, setCreatedSessionId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadDone, setUploadDone] = useState(false);

  useEffect(() => {
    setDeviceId("");
    setCrew([]);
    if (!boatId) {
      setDevices([]);
      setBoatMembers([]);
      return;
    }
    devicesService.list().then((all) => setDevices(all.filter((d) => d.default_boat_id === boatId)));
    boatsService.listMembers(boatId).then(setBoatMembers);
  }, [boatId]);

  const availableMembers = boatMembers.filter((m) => !crew.some((c) => c.user_id === m.user_id));
  const addMember = (m: BoatMember) => setCrew((c) => [...c, { user_id: m.user_id, boat_role: m.role }]);
  const addGuest = () => setCrew((c) => [...c, { guest_name: "", boat_role: "crew" }]);
  const setSlot = (i: number, patch: Partial<CrewSlot>) =>
    setCrew((c) => c.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const rmSlot = (i: number) => setCrew((c) => c.filter((_, j) => j !== i));

  const memberLabel = (userId: number) => {
    const m = boatMembers.find((mm) => mm.user_id === userId);
    return m?.name || m?.email || `#${userId}`;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const cleaned = crew
        .filter((s) => s.user_id != null || (s.guest_name ?? "").trim())
        .map((s) =>
          s.user_id != null
            ? { user_id: s.user_id, boat_role: s.boat_role || null }
            : { guest_name: s.guest_name!.trim(), boat_role: s.boat_role || null },
        );
      const created = await sessionsService.create({
        boat_id: boatId,
        date,
        device_id: deviceId || null,
        crew: cleaned,
      });
      if (created.source === "manual") {
        setCreatedSessionId(created.id);
        setStep("upload");
        setBusy(false);
      } else {
        onDone();
      }
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  const uploadGpx = async () => {
    if (!file || createdSessionId == null) return;
    setBusy(true);
    setErr(null);
    try {
      const { url } = await sessionsService.getGpxUploadUrl(createdSessionId);
      await sessionsService.uploadGpxFile(url, file);
      await sessionsService.completeGpxUpload(createdSessionId);
      setUploadDone(true);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
    } finally {
      setBusy(false);
    }
  };

  if (step === "upload") {
    return (
      <Modal title={t("mysessions.uploadGpx")} onClose={onDone}>
        {uploadDone ? (
          <p className="sf-muted">{t("mysessions.gpxUploaded")}</p>
        ) : (
          <div className="sf-form">
            <p className="sf-muted">{t("mysessions.uploadGpxHint")}</p>
            <input
              type="file"
              accept=".gpx"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            {err && <p className="sf-error">{err}</p>}
            <Button onClick={uploadGpx} disabled={!file || busy}>
              {busy ? t("auth.pleaseWait") : t("mysessions.upload")}
            </Button>
          </div>
        )}
        <Button variant="ghost" className="sf-mt" onClick={onDone}>
          {uploadDone ? t("common.close") : t("mysessions.uploadLater")}
        </Button>
      </Modal>
    );
  }

  return (
    <Modal title={t("mysessions.create")} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        <Select
          id="new-sess-boat"
          label={t("mysessions.boat")}
          value={boatId}
          onChange={(e) => setBoatId(e.target.value)}
          required
        >
          <option value="">{t("mysessions.selectBoat")}</option>
          {myBoats.map((b: Boat) => (
            <option key={b.boat_id} value={b.boat_id}>{b.name || b.boat_id}</option>
          ))}
        </Select>

        <label className="sf-field" htmlFor="new-sess-date">
          <span className="sf-field__label">{t("mysessions.date")}</span>
          <input
            id="new-sess-date"
            type="date"
            className="sf-field__input"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </label>

        {boatId && (
          <Select
            id="new-sess-device"
            label={t("mysessions.device")}
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
          >
            <option value="">{t("mysessions.deviceNone")}</option>
            {devices.map((d) => (
              <option key={d.device_id} value={d.device_id}>{d.name || d.device_id}</option>
            ))}
          </Select>
        )}

        {boatId && (
          <div className="sf-crew">
            <span className="sf-field__label">{t("mysessions.crew")}</span>
            {crew.map((s, i) => (
              <div key={i} className="sf-crew__row">
                {s.user_id != null ? (
                  <span className="sf-field__input">{memberLabel(s.user_id)}</span>
                ) : (
                  <input
                    className="sf-field__input"
                    placeholder={t("mysessions.guestName")}
                    value={s.guest_name ?? ""}
                    onChange={(e) => setSlot(i, { guest_name: e.target.value })}
                  />
                )}
                <input
                  className="sf-field__input"
                  placeholder={t("mysessions.role")}
                  value={s.boat_role ?? ""}
                  onChange={(e) => setSlot(i, { boat_role: e.target.value })}
                />
                <button type="button" className="sf-btn sf-btn--ghost" onClick={() => rmSlot(i)}>×</button>
              </div>
            ))}

            {availableMembers.length > 0 && (
              <Select
                id="new-sess-add-member"
                label={t("mysessions.addMember")}
                value=""
                onChange={(e) => {
                  const m = availableMembers.find((mm) => String(mm.user_id) === e.target.value);
                  if (m) addMember(m);
                }}
              >
                <option value="">{t("mysessions.selectMember")}</option>
                {availableMembers.map((m) => (
                  <option key={m.user_id} value={m.user_id}>{m.name || m.email || `#${m.user_id}`}</option>
                ))}
              </Select>
            )}
            <button type="button" className="sf-btn sf-btn--ghost" onClick={addGuest}>
              + {t("mysessions.addCrew")}
            </button>
          </div>
        )}

        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy || !boatId || !date}>
          {busy ? t("auth.pleaseWait") : t("mysessions.create")}
        </Button>
      </form>
    </Modal>
  );
}
