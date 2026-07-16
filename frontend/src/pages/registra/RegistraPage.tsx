import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { boatsService, boatKeys } from "@/services/boats";
import { activitiesService, activityKeys } from "@/services/activities";
import { sessionsService } from "@/services/sessions";
import { useImportUpload } from "@/hooks/useImportUpload";
import * as nativeRecording from "@/services/nativeRecording";
import type { RecordingMeta } from "@/services/nativeRecording";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import type { UUID } from "@/types";

const STANDALONE = "" as const; // empty select value = "uscita singola"

function ActivityPicker({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useTranslation();
  const activities = useQuery({
    queryKey: activityKeys.list({ mine: "true" }),
    queryFn: () => activitiesService.list({ mine: true }),
  });
  return (
    <Select label={t("registra.linkTo")} id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value={STANDALONE}>{t("registra.standalone")}</option>
      {activities.data?.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name ?? a.id}
        </option>
      ))}
    </Select>
  );
}

function elapsedLabel(startedAt: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function RecordingRow({ recording, onChanged }: { recording: RecordingMeta; onChanged: () => void }) {
  const { t } = useTranslation();
  const [activityId, setActivityId] = useState(recording.activityId ?? STANDALONE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const upload = useImportUpload();

  const boats = useQuery({ queryKey: boatKeys.mine, queryFn: () => boatsService.list(true) });
  const boatName = boats.data?.find((b) => b.id === recording.boatId)?.name ?? recording.boatId;

  const doUpload = async () => {
    setBusy(true);
    setError(null);
    try {
      await nativeRecording.setStatus(recording.id, "uploading");
      onChanged();
      const file = await nativeRecording.readRecordingGpx(recording.id);
      const completed = await upload.start(file, {
        boatId: recording.boatId,
        activityId: recording.activityId ?? undefined,
      });
      await nativeRecording.setStatus(recording.id, "uploaded", completed.session_id ?? undefined);
    } catch (e) {
      await nativeRecording.setStatus(recording.id, "failed");
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  const doReassign = async () => {
    setBusy(true);
    setError(null);
    try {
      if (recording.sessionId && activityId) {
        // Already uploaded: move the standalone session server-side.
        await sessionsService.attachToActivity(recording.sessionId, activityId as UUID);
      }
      await nativeRecording.setActivity(recording.id, activityId ? (activityId as UUID) : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  const doRemove = async () => {
    await nativeRecording.remove(recording.id);
    onChanged();
  };

  return (
    <Card>
      <p className="sf-field__label">
        {new Date(recording.startedAt).toLocaleString()} — {boatName}
      </p>
      <p className="sf-muted">
        {t(`registra.status.${recording.status}`)} · {recording.pointCount} {t("registra.points")}
      </p>
      <ActivityPicker id={`activity-${recording.id}`} value={activityId} onChange={setActivityId} />
      <div className="sf-form__actions">
        {recording.status === "stopped" && (
          <Button onClick={() => void doUpload()} disabled={busy}>
            {t("registra.upload")}
          </Button>
        )}
        {activityId !== (recording.activityId ?? STANDALONE) && (
          <Button variant="ghost" onClick={() => void doReassign()} disabled={busy}>
            {t("registra.reassign")}
          </Button>
        )}
        {recording.status !== "recording" && recording.status !== "uploading" && (
          <Button variant="danger" onClick={() => void doRemove()} disabled={busy}>
            {t("common.delete")}
          </Button>
        )}
      </div>
      {error && <p className="sf-form__error">{error}</p>}
    </Card>
  );
}

export function RegistraPage() {
  const { t } = useTranslation();
  const { recordings, refresh } = nativeRecording.useRecordings();
  const [boatId, setBoatId] = useState("");
  const [activityId, setActivityId] = useState<string>(STANDALONE);
  const [activeId, setActiveId] = useState<UUID | null>(nativeRecording.activeRecordingId());
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0);

  const boats = useQuery({ queryKey: boatKeys.mine, queryFn: () => boatsService.list(true) });

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Live-updating elapsed-time display while a recording is running.
  useEffect(() => {
    if (!activeId) return;
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [activeId]);

  const active = recordings.find((r) => r.id === activeId);

  const onStart = async () => {
    setError(null);
    try {
      const id = await nativeRecording.start(boatId as UUID, activityId ? (activityId as UUID) : null);
      setActiveId(id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onStop = async () => {
    await nativeRecording.stop();
    setActiveId(null);
    refresh();
  };

  return (
    <>
      <Card title={t("registra.title")}>
        {active ? (
          <>
            <p className="sf-badge sf-badge--success">{t("registra.recording")}</p>
            <p className="sf-field__label">{elapsedLabel(active.startedAt)}</p>
            <p className="sf-muted">
              {active.pointCount} {t("registra.points")}
            </p>
            <div className="sf-form__actions">
              <Button variant="danger" onClick={() => void onStop()}>
                {t("registra.stop")}
              </Button>
            </div>
          </>
        ) : (
          <>
            <Select
              label={t("sessions.importBoat")}
              id="registra-boat"
              value={boatId}
              onChange={(e) => setBoatId(e.target.value)}
              required
            >
              <option value="" disabled>
                …
              </option>
              {boats.data?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
            <ActivityPicker id="registra-activity" value={activityId} onChange={setActivityId} />
            <div className="sf-form__actions">
              <Button onClick={() => void onStart()} disabled={!boatId}>
                {t("registra.start")}
              </Button>
            </div>
            {error && <p className="sf-form__error">{error}</p>}
          </>
        )}
      </Card>
      {recordings
        .filter((r) => r.id !== activeId)
        .map((r) => (
          <RecordingRow key={r.id} recording={r} onChanged={refresh} />
        ))}
      {recordings.length === 0 && !active && <p className="sf-muted">{t("registra.empty")}</p>}
    </>
  );
}
