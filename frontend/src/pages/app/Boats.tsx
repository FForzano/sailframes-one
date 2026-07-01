import { useState } from "react";
import { useTranslation } from "react-i18next";
import { boatsService } from "@/services/boats.service";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { InputField } from "@/components/ui/InputField";
import type { Boat, BoatWrite } from "@/types";

export function Boats() {
  const { t } = useTranslation();
  const { refresh } = useAuth();
  const caps = useCapabilities();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(() => boatsService.list(), []);
  const [editing, setEditing] = useState<Boat | null>(null);
  const [creating, setCreating] = useState(false);

  const afterChange = async () => {
    reload();
    await refresh();
  };

  const canManage = (b: Boat) =>
    caps.isBoatOwner(b.boat_id) || caps.isBoatSkipper(b.boat_id) || caps.can("boat.edit", b.club_id ?? undefined);

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("nav.boats")}</h1>
        <Button onClick={() => setCreating(true)}>{t("boats.create")}</Button>
      </div>

      <div className="sf-cardgrid">
        {(data ?? []).map((b) => (
          <section key={b.boat_id} className="sf-card">
            <div className="sf-card__name">
              {b.name || b.boat_id}
              {caps.isBoatOwner(b.boat_id) && (
                <span className="sf-chip sf-chip--sm">{t("boats.owner")}</span>
              )}
            </div>
            <div className="sf-muted">
              {[b.type, b.sail_number, b.club].filter(Boolean).join(" · ") || b.boat_id}
            </div>
            <div className="sf-muted">
              {t("boats.crewCount", { count: b.members?.length ?? 0 })}
            </div>
            {canManage(b) && (
              <div className="sf-card__actions">
                <Button variant="ghost" onClick={() => setEditing(b)}>
                  {t("boats.edit")}
                </Button>
              </div>
            )}
          </section>
        ))}
      </div>

      {creating && (
        <BoatFormModal
          title={t("boats.create")}
          submitLabel={t("boats.create")}
          initial={{}}
          requireId
          onClose={() => setCreating(false)}
          onSubmit={async (body) => {
            await boatsService.create(body);
            notify(t("boats.created"), "success");
            setCreating(false);
            await afterChange();
          }}
        />
      )}

      {editing && (
        <BoatFormModal
          title={`${t("boats.edit")} · ${editing.name || editing.boat_id}`}
          submitLabel={t("boats.save")}
          initial={editing}
          onClose={() => setEditing(null)}
          onSubmit={async (body) => {
            await boatsService.update(editing.boat_id, body);
            notify(t("boats.saved"), "success");
            setEditing(null);
            await afterChange();
          }}
        />
      )}
    </div>
  );
}

function BoatFormModal({
  title,
  submitLabel,
  initial,
  requireId,
  onClose,
  onSubmit,
}: {
  title: string;
  submitLabel: string;
  initial: Partial<Boat>;
  requireId?: boolean;
  onClose: () => void;
  onSubmit: (body: BoatWrite) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [f, setF] = useState<BoatWrite>({
    boat_id: initial.boat_id ?? "",
    name: initial.name ?? "",
    type: initial.type ?? "",
    sail_number: initial.sail_number ?? "",
    club: initial.club ?? "",
    notes: initial.notes ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof BoatWrite) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      // On edit, boat_id is immutable and must not be sent.
      const body = requireId ? f : { ...f, boat_id: undefined };
      await onSubmit(body);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        {requireId && (
          <InputField id="boat-id" label={t("boats.boatId")} value={f.boat_id} onChange={set("boat_id")} required />
        )}
        <InputField id="boat-name" label={t("boats.name")} value={f.name} onChange={set("name")} />
        <InputField id="boat-type" label={t("boats.type")} value={f.type} onChange={set("type")} />
        <InputField id="boat-sail" label={t("boats.sailNumber")} value={f.sail_number} onChange={set("sail_number")} />
        <InputField id="boat-club" label={t("boats.club")} value={f.club} onChange={set("club")} />
        <InputField id="boat-notes" label={t("boats.notes")} value={f.notes} onChange={set("notes")} />
        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy || (requireId && !f.boat_id?.trim())}>
          {busy ? t("auth.pleaseWait") : submitLabel}
        </Button>
      </form>
    </Modal>
  );
}
