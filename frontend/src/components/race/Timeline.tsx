import { timeController, useTimeState } from "@/stores/timeController";
import { fmtTime } from "@/utils/format";

// Compact transport bar: step back, play/pause, step forward, a speed-cycle
// button, and the clock. The speed chart itself is the scrubber (drag/tap to
// seek) — no separate progress bar, so this row stays narrow on mobile.
export function Timeline({
  stepMs = 5000,
  className = "",
}: {
  stepMs?: number;
  /** Extra class, e.g. "sf-timeline--overlay" when floated on top of the map. */
  className?: string;
}) {
  const { tMin, tMax, cursor, playing, speed } = useTimeState();

  return (
    <div className={`sf-timeline ${className}`}>
      <button
        className="sf-btn sf-btn--ghost sf-btn--sm"
        onClick={() => timeController.step(-stepMs)}
        aria-label="Step back"
      >
        ⏮
      </button>
      <button
        className="sf-btn sf-btn--primary sf-btn--sm"
        onClick={() => timeController.toggle()}
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? "⏸" : "▶"}
      </button>
      <button
        className="sf-btn sf-btn--ghost sf-btn--sm"
        onClick={() => timeController.step(stepMs)}
        aria-label="Step forward"
      >
        ⏭
      </button>
      <button
        className="sf-btn sf-btn--ghost sf-btn--sm sf-timeline__speed"
        onClick={() => timeController.cycleSpeed()}
        aria-label="Cycle playback speed"
      >
        {speed}×
      </button>
      <span className="sf-timeline__clock">{tMax > tMin ? fmtTime(cursor) : "--:--:--"}</span>
    </div>
  );
}
