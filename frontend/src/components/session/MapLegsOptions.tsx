import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useClickOutside } from "@/hooks/useClickOutside";

/** Floating ⚙ popover (rendered via `MapView`'s `mapOptions` overlay slot) for
 * toggling the legs/maneuvers markers on the session map. */
export function MapLegsOptions({
  showLegs,
  onShowLegsChange,
  showManeuvers,
  onShowManeuversChange,
}: {
  showLegs: boolean;
  onShowLegsChange: (v: boolean) => void;
  showManeuvers: boolean;
  onShowManeuversChange: (v: boolean) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, () => setOpen(false));

  return (
    <div className="sf-options" ref={ref}>
      <button
        type="button"
        className="sf-btn sf-btn--ghost sf-btn--sm"
        aria-label="Map options"
        onClick={() => setOpen((v) => !v)}
      >
        ⚙
      </button>
      {open && (
        <div className="sf-options__panel">
          <label className="sf-check">
            <input
              type="checkbox"
              checked={showLegs}
              onChange={(e) => onShowLegsChange(e.target.checked)}
            />
            <span>{t("sessions.showLegs")}</span>
          </label>
          <label className="sf-check">
            <input
              type="checkbox"
              checked={showManeuvers}
              onChange={(e) => onShowManeuversChange(e.target.checked)}
            />
            <span>{t("sessions.showManeuvers")}</span>
          </label>
        </div>
      )}
    </div>
  );
}
