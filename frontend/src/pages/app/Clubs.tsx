import { useState } from "react";
import { useTranslation } from "react-i18next";
import { clubsService } from "@/services/clubs.service";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { InputField } from "@/components/ui/InputField";
import type { Club } from "@/types";

export function Clubs() {
  const { t } = useTranslation();
  const { refresh } = useAuth();
  const caps = useCapabilities();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(() => clubsService.list(), []);
  const [creating, setCreating] = useState(false);

  const afterChange = async () => {
    reload();
    await refresh(); // memberships changed → nav/dashboard update
  };

  const onCreate = async (name: string) => {
    await clubsService.create(name);
    notify(t("clubs.created"), "success");
    setCreating(false);
    await afterChange();
  };

  const onJoin = async (club: Club) => {
    try {
      await clubsService.join(club.id);
      notify(t("clubs.joined"), "success");
      await afterChange();
    } catch (e) {
      notify(e instanceof ApiError ? e.detail : t("auth.genericError"), "error");
    }
  };

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("nav.clubs")}</h1>
        <Button onClick={() => setCreating(true)}>{t("clubs.create")}</Button>
      </div>

      <div className="sf-cardgrid">
        {(data ?? []).map((club) => {
          const owns = caps.ownsClub(club.id);
          const member = owns || caps.memberOfClub(club.id);
          return (
            <section key={club.id} className="sf-card">
              <div className="sf-card__name">{club.name}</div>
              <div className="sf-muted">
                {t("clubs.memberCount", { count: club.members?.length ?? 0 })}
                {owns && <span className="sf-chip sf-chip--sm">{t("clubs.owner")}</span>}
                {!owns && member && <span className="sf-chip sf-chip--sm">{t("clubs.member")}</span>}
              </div>
              <div className="sf-card__actions">
                {!member && (
                  <Button variant="ghost" onClick={() => onJoin(club)}>
                    {t("clubs.join")}
                  </Button>
                )}
                {owns && <InviteButton club={club} onDone={afterChange} />}
              </div>
            </section>
          );
        })}
      </div>

      {creating && (
        <CreateClubModal onClose={() => setCreating(false)} onCreate={onCreate} />
      )}
    </div>
  );
}

function CreateClubModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await onCreate(name);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  return (
    <Modal title={t("clubs.create")} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        <InputField
          id="club-name"
          label={t("clubs.name")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy || !name.trim()}>
          {busy ? t("auth.pleaseWait") : t("clubs.create")}
        </Button>
      </form>
    </Modal>
  );
}

// Invite by user id — a lightweight inline form matching the backend contract
// (users are referenced by numeric id; a directory picker is a later nicety).
function InviteButton({ club, onDone }: { club: Club; onDone: () => Promise<void> }) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [open, setOpen] = useState(false);
  const [userId, setUserId] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const id = parseInt(userId, 10);
    if (!id) return;
    setBusy(true);
    try {
      await clubsService.invite(club.id, id);
      notify(t("clubs.invited"), "success");
      setOpen(false);
      setUserId("");
      await onDone();
    } catch (e2) {
      notify(e2 instanceof ApiError ? e2.detail : t("auth.genericError"), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button variant="ghost" onClick={() => setOpen(true)}>
        {t("clubs.invite")}
      </Button>
      {open && (
        <Modal title={`${t("clubs.invite")} · ${club.name}`} onClose={() => setOpen(false)}>
          <form className="sf-form" onSubmit={submit}>
            <InputField
              id={`invite-${club.id}`}
              label={t("clubs.userId")}
              type="number"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
            />
            <Button type="submit" disabled={busy}>
              {busy ? t("auth.pleaseWait") : t("clubs.invite")}
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}
