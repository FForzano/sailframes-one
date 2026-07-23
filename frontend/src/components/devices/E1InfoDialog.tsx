import { useTranslation } from "react-i18next";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { E1_REPO_URL } from "@/config/links";
import { E1_INFO_BULLET_KEYS } from "./e1Info";

export function E1InfoDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <Modal title={t("devices.e1.info.title")} onClose={onClose}>
      <p className="sf-muted">{t("devices.e1.info.intro")}</p>
      <ul>
        {E1_INFO_BULLET_KEYS.map((key) => (
          <li key={key}>{t(`devices.e1.info.bullets.${key}`)}</li>
        ))}
      </ul>
      <p className="sf-muted">{t("devices.e1.info.diyNote")}</p>
      <div className="sf-form__actions">
        <a href={E1_REPO_URL} target="_blank" rel="noreferrer">
          <Button variant="ghost">{t("devices.e1.info.repoLink")}</Button>
        </a>
        <Button onClick={onClose}>{t("common.close")}</Button>
      </div>
    </Modal>
  );
}
