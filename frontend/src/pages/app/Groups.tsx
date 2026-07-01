import { useState } from "react";
import { useTranslation } from "react-i18next";
import { groupsService } from "@/services/groups.service";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/hooks/useAuth";
import { useCapabilities } from "@/hooks/useCapabilities";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { InputField } from "@/components/ui/InputField";
import type { Group } from "@/types";

export function Groups() {
  const { t } = useTranslation();
  const { user, refresh } = useAuth();
  const caps = useCapabilities();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(() => groupsService.list(), []);
  const [creating, setCreating] = useState(false);

  const afterChange = async () => {
    reload();
    await refresh();
  };

  const isAdmin = (g: Group) =>
    caps.isSuperadmin ||
    g.members?.some((m) => m.user_id === user?.id && m.role === "admin" && m.status === "active");

  const onJoin = async (g: Group) => {
    try {
      await groupsService.join(g.id);
      notify(t("groups.joined"), "success");
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
        <h1 className="sf-page__title">{t("nav.groups")}</h1>
        <Button onClick={() => setCreating(true)}>{t("groups.create")}</Button>
      </div>

      <div className="sf-cardgrid">
        {(data ?? []).map((g) => {
          const member = caps.memberOfGroup(g.id) || isAdmin(g);
          return (
            <section key={g.id} className="sf-card">
              <div className="sf-card__name">{g.name}</div>
              {g.description && <div className="sf-muted">{g.description}</div>}
              <div className="sf-muted">
                {t("clubs.memberCount", { count: g.members?.length ?? 0 })}
                {isAdmin(g) && <span className="sf-chip sf-chip--sm">{t("groups.admin")}</span>}
                {!isAdmin(g) && member && (
                  <span className="sf-chip sf-chip--sm">{t("clubs.member")}</span>
                )}
              </div>
              <div className="sf-card__actions">
                {!member && (
                  <Button variant="ghost" onClick={() => onJoin(g)}>
                    {t("clubs.join")}
                  </Button>
                )}
                {isAdmin(g) && <InviteGroupButton group={g} onDone={afterChange} />}
              </div>
            </section>
          );
        })}
      </div>

      {creating && (
        <CreateGroupModal
          onClose={() => setCreating(false)}
          onDone={async () => {
            setCreating(false);
            await afterChange();
          }}
        />
      )}
    </div>
  );
}

function CreateGroupModal({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await groupsService.create(name, desc || undefined);
      notify(t("groups.created"), "success");
      await onDone();
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  return (
    <Modal title={t("groups.create")} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        <InputField id="group-name" label={t("clubs.name")} value={name} onChange={(e) => setName(e.target.value)} required />
        <InputField id="group-desc" label={t("groups.description")} value={desc} onChange={(e) => setDesc(e.target.value)} />
        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy || !name.trim()}>
          {busy ? t("auth.pleaseWait") : t("groups.create")}
        </Button>
      </form>
    </Modal>
  );
}

function InviteGroupButton({ group, onDone }: { group: Group; onDone: () => Promise<void> }) {
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
      await groupsService.invite(group.id, id);
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
        <Modal title={`${t("clubs.invite")} · ${group.name}`} onClose={() => setOpen(false)}>
          <form className="sf-form" onSubmit={submit}>
            <InputField id={`ginvite-${group.id}`} label={t("clubs.userId")} type="number" value={userId} onChange={(e) => setUserId(e.target.value)} required />
            <Button type="submit" disabled={busy}>
              {busy ? t("auth.pleaseWait") : t("clubs.invite")}
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}
