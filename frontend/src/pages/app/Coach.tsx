import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { coachService, type Briefing } from "@/services/coach.service";
import { GoogleSignIn } from "@/components/coach/GoogleSignIn";
import { useToast } from "@/hooks/useToast";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { fmtShortDate } from "@/utils/format";

// Coach area folded into the member app as a route, but running on its own
// (separate) auth + backend. If the coach API isn't configured for this deploy,
// the nav entry is hidden; reaching here directly shows a notice.
export function Coach() {
  const { t } = useTranslation();
  const { notify } = useToast();
  const [authed, setAuthed] = useState(coachService.hasValidToken());
  const [briefings, setBriefings] = useState<Briefing[] | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setBriefings(await coachService.listBriefings());
    } catch (e) {
      notify(String(e), "error");
      if (String(e).includes("unauthorized")) setAuthed(false);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  const onCredential = useCallback(
    async (idToken: string) => {
      try {
        const email = JSON.parse(atob(idToken.split(".")[1])).email as string;
        await coachService.exchange(idToken, email);
        setAuthed(true);
        void load();
      } catch (e) {
        notify(String(e), "error");
      }
    },
    [load, notify],
  );

  if (!coachService.isConfigured()) {
    return (
      <div className="sf-page">
        <h1 className="sf-page__title">{t("coach.title")}</h1>
        <p className="sf-muted">{t("coach.notConfigured")}</p>
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="sf-page">
        <h1 className="sf-page__title">{t("coach.title")}</h1>
        <Card title={t("coach.signIn")}>
          <p className="sf-muted">{t("coach.signInHint")}</p>
          <GoogleSignIn onCredential={onCredential} />
        </Card>
      </div>
    );
  }

  // Kick off first load lazily once authed.
  if (briefings === null && !loading) void load();

  return (
    <div className="sf-page">
      <div className="sf-toolbar">
        <h1 className="sf-page__title">{t("coach.title")}</h1>
        <span className="sf-muted">{coachService.getEmail()}</span>
        <button
          className="sf-btn sf-btn--ghost"
          onClick={() => {
            coachService.clear();
            setAuthed(false);
            setBriefings(null);
          }}
        >
          {t("auth.logout")}
        </button>
      </div>

      {loading ? (
        <Spinner full />
      ) : briefings && briefings.length > 0 ? (
        <div className="sf-list">
          {briefings.map((b) => (
            <div key={`${b.race_id}/${b.device_id}`} className="sf-listrow">
              <span className="sf-listrow__main">
                {b.race_name || b.race_id} · {b.boat_name || b.device_id}
              </span>
              <span className="sf-listrow__meta">{fmtShortDate(b.created_at?.slice(0, 10))}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="sf-muted">{t("coach.noBriefings")}</p>
      )}
    </div>
  );
}
