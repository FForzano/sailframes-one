import { useState } from "react";
import { useTranslation } from "react-i18next";
import { devicesService } from "@/services/devices.service";
import { boatsService } from "@/services/boats.service";
import { clubsService } from "@/services/clubs.service";
import { useResource } from "@/hooks/useResource";
import { useCapabilities } from "@/hooks/useCapabilities";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { InputField } from "@/components/ui/InputField";
import { Select } from "@/components/ui/Select";
import type { Device, OwnerType } from "@/types";

export function Devices() {
  const { t } = useTranslation();
  const caps = useCapabilities();
  const { notify } = useToast();
  const { data, loading, error, reload } = useResource(
    () =>
      Promise.all([devicesService.list(), boatsService.list(), clubsService.list()]).then(
        ([devices, boats, clubs]) => ({ devices, boats, clubs }),
      ),
    [],
  );
  const [registering, setRegistering] = useState(false);

  if (loading && !data) return <Spinner full />;
  if (error) return <p className="sf-error">{error}</p>;

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("nav.devices")}</h1>
        {(caps.canManageAnyBoat || caps.canManageAnyClub) && (
          <Button onClick={() => setRegistering(true)}>{t("devices.register")}</Button>
        )}
      </div>

      <div className="sf-tablewrap">
        <table className="sf-table">
          <thead>
            <tr>
              <th>{t("devices.id")}</th>
              <th>{t("devices.name")}</th>
              <th>{t("devices.type")}</th>
              <th>{t("devices.owner")}</th>
              <th>{t("devices.boat")}</th>
              <th>{t("devices.status")}</th>
            </tr>
          </thead>
          <tbody>
            {(data?.devices ?? []).map((d) => (
              <tr key={d.device_id}>
                <td>{d.device_id}</td>
                <td>{d.name || "—"}</td>
                <td>{d.device_type}</td>
                <td>{d.owner_type === "club" ? `club ${d.owned_by_club_id}` : t("devices.private")}</td>
                <td>{d.default_boat_id || "—"}</td>
                <td>{d.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {registering && data && (
        <RegisterModal
          boats={data.boats.map((b) => ({ id: b.boat_id, label: b.name || b.boat_id }))}
          clubs={data.clubs
            .filter((c) => caps.ownsClub(c.id) || caps.can("raceday.manage", c.id))
            .map((c) => ({ id: c.id, label: c.name }))}
          onClose={() => setRegistering(false)}
          onDone={(dev) => {
            notify(t("devices.registered", { id: dev.device_id }), "success");
            setRegistering(false);
            reload();
          }}
        />
      )}
    </div>
  );
}

function RegisterModal({
  boats,
  clubs,
  onClose,
  onDone,
}: {
  boats: Array<{ id: string; label: string }>;
  clubs: Array<{ id: number; label: string }>;
  onClose: () => void;
  onDone: (dev: Device) => void;
}) {
  const { t } = useTranslation();
  const [ownerType, setOwnerType] = useState<OwnerType>(boats.length ? "user" : "club");
  const [name, setName] = useState("");
  const [boatId, setBoatId] = useState(boats[0]?.id ?? "");
  const [clubId, setClubId] = useState(clubs[0]?.id ?? 0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const dev = await devicesService.register(
        ownerType === "user"
          ? { owner_type: "user", name: name || undefined, default_boat_id: boatId }
          : { owner_type: "club", name: name || undefined, owned_by_club_id: clubId },
      );
      onDone(dev);
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.detail : t("auth.genericError"));
      setBusy(false);
    }
  };

  return (
    <Modal title={t("devices.register")} onClose={onClose}>
      <form className="sf-form" onSubmit={submit}>
        <Select id="dev-owner" label={t("devices.ownerType")} value={ownerType} onChange={(e) => setOwnerType(e.target.value as OwnerType)}>
          {boats.length > 0 && <option value="user">{t("devices.boatPrivate")}</option>}
          {clubs.length > 0 && <option value="club">{t("devices.clubDevice")}</option>}
        </Select>
        <InputField id="dev-name" label={t("devices.name")} value={name} onChange={(e) => setName(e.target.value)} />
        {ownerType === "user" ? (
          <Select id="dev-boat" label={t("devices.boat")} value={boatId} onChange={(e) => setBoatId(e.target.value)} required>
            {boats.map((b) => (
              <option key={b.id} value={b.id}>{b.label}</option>
            ))}
          </Select>
        ) : (
          <Select id="dev-club" label={t("nav.clubs")} value={clubId} onChange={(e) => setClubId(parseInt(e.target.value, 10))} required>
            {clubs.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </Select>
        )}
        {err && <p className="sf-error">{err}</p>}
        <Button type="submit" disabled={busy}>
          {busy ? t("auth.pleaseWait") : t("devices.register")}
        </Button>
      </form>
    </Modal>
  );
}
