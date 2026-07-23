import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Capacitor } from "@capacitor/core";
import { Modal } from "@/components/ui/Modal";
import { ClaimDeviceDialog } from "@/components/common/ClaimDeviceDialog";
import type { UUID } from "@/types";
import styles from "./AddDeviceDialog.module.css";

type Owner = { owner_user_id?: UUID; owner_boat_id?: UUID; owner_club_id?: UUID };

function DeviceOptionCard({
  title,
  hint,
  disabled,
  badge,
  onClick,
}: {
  title: string;
  hint: string;
  disabled?: boolean;
  /** Shown when `disabled` — defaults to `devices.add.soon`. Pass an
   * explicit label when the card is disabled for a different reason (e.g.
   * "app only" rather than "not built yet"), so the two aren't conflated. */
  badge?: string;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className={`sf-card ${styles.card}`}
      disabled={disabled}
      onClick={onClick}
    >
      <span className={styles.cardTitle}>{title}</span>
      <span className={`sf-muted ${styles.cardHint}`}>{hint}</span>
      {disabled && <span className="sf-badge sf-badge--soon">{badge ?? t("devices.add.soon")}</span>}
    </button>
  );
}

/** Entry point for "add a device", opened in place of the old direct
 * ClaimDeviceDialog trigger (docs/device-protocol.md §8 for the XGSail E1
 * BLE flow this leads into). Only XGSail E1 is active today; Apple Watch,
 * Garmin and Polar are shown disabled ("in arrivo") — see
 * backend/routers/integrations.py, which reserves their API surface without
 * implementing it yet. XGSail E1 itself is disabled on web (BLE claiming
 * needs the native app) but tagged "solo app", not "in arrivo", since it's
 * available today — just not from this platform.
 *
 * Context-aware on `owner`: wearables are personal (a user connects their
 * own watch/account), so they're only offered from the personal devices
 * page (`owner_user_id`) — a boat or club claim only ever adds hardware. */
export function AddDeviceDialog({ owner, onClose }: { owner: Owner; onClose: () => void }) {
  const { t } = useTranslation();
  const [claimingXgsailE1, setClaimingXgsailE1] = useState(false);
  const isNative = Capacitor.isNativePlatform();
  const showWearables = owner.owner_user_id !== undefined;

  if (claimingXgsailE1) {
    return <ClaimDeviceDialog owner={owner} onClose={onClose} />;
  }

  return (
    <Modal title={t("devices.add.title")} onClose={onClose}>
      <div className={styles.grid}>
        <DeviceOptionCard
          title={t("devices.add.xgsailE1")}
          hint={isNative ? t("devices.add.xgsailE1Hint") : t("devices.add.nativeOnly")}
          disabled={!isNative}
          badge={t("devices.add.nativeOnlyBadge")}
          onClick={() => setClaimingXgsailE1(true)}
        />
        {showWearables && (
          <>
            <DeviceOptionCard title={t("devices.add.appleWatch")} hint="" disabled onClick={() => {}} />
            <DeviceOptionCard title={t("devices.add.garmin")} hint="" disabled onClick={() => {}} />
            <DeviceOptionCard title={t("devices.add.polar")} hint="" disabled onClick={() => {}} />
          </>
        )}
      </div>
      {!showWearables && <p className="sf-muted">{t("devices.add.personalOnly")}</p>}
      {isNative && owner.owner_boat_id === undefined && (
        <p className="sf-badge sf-badge--warning">{t("devices.add.xgsailE1NoBoatWarning")}</p>
      )}
    </Modal>
  );
}
