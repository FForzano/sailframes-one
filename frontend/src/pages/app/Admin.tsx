import { useState } from "react";
import { useTranslation } from "react-i18next";
import { adminService, type CleanupPreview } from "@/services/admin.service";
import { useToast } from "@/hooks/useToast";
import { ApiError } from "@/utils/api";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

// Admin utilities. Currently: bulk session cleanup (preview → delete). The
// backend runs dry_run by default, so a preview is always safe; deletion is a
// separate confirmed action.
export function Admin() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [maxDuration, setMaxDuration] = useState(15);
  const [requireBoat, setRequireBoat] = useState(true);
  const [preview, setPreview] = useState<CleanupPreview | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (dryRun: boolean) => {
    if (!dryRun && !window.confirm(t("admin.confirmDelete"))) return;
    setBusy(true);
    try {
      const res = await adminService.cleanupSessions({
        maxDurationMinutes: maxDuration,
        requireBoat,
        dryRun,
      });
      setPreview(res);
      if (!dryRun) notify(t("admin.cleanupDone"), "success");
    } catch (e) {
      notify(e instanceof ApiError ? e.detail : t("auth.genericError"), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sf-page">
      <h1 className="sf-page__title">{t("nav.admin")}</h1>

      <Card title={t("admin.cleanupTitle")}>
        <p className="sf-muted">{t("admin.cleanupBody")}</p>
        <div className="sf-crew__row">
          <label className="sf-field">
            <span className="sf-field__label">{t("admin.maxDuration")}</span>
            <input
              className="sf-field__input"
              type="number"
              value={maxDuration}
              onChange={(e) => setMaxDuration(parseInt(e.target.value, 10) || 0)}
            />
          </label>
          <label className="sf-checkbox">
            <input type="checkbox" checked={requireBoat} onChange={(e) => setRequireBoat(e.target.checked)} />
            {t("admin.requireBoat")}
          </label>
        </div>
        <div className="sf-btnrow sf-mt">
          <Button variant="ghost" onClick={() => run(true)} disabled={busy}>
            {t("admin.preview")}
          </Button>
          <Button variant="danger" onClick={() => run(false)} disabled={busy || !preview}>
            {t("admin.delete")}
          </Button>
        </div>

        {preview && (
          <div className="sf-mt">
            <p className="sf-muted">
              {t("admin.willDelete", { count: preview.to_delete.length })}
              {preview.dry_run ? ` · ${t("admin.dryRun")}` : ""}
            </p>
            <ul className="sf-plainlist">
              {preview.to_delete.slice(0, 50).map((s) => (
                <li key={`${s.device_id}/${s.date}`}>
                  {s.device_id}/{s.date} · {s.duration_minutes}min · {s.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
