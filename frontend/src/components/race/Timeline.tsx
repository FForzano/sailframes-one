import { timeController, useTimeState } from "@/stores/timeController";

const SPEEDS = [1, 2, 4, 8];

function fmtClock(ms: number): string {
  if (!ms) return "--:--:--";
  return new Date(ms).toLocaleTimeString(undefined, { hour12: false });
}

// Transport bar: play/pause, speed multipliers, a scrub range, and the clock.
export function Timeline() {
  const { tMin, tMax, cursor, playing, speed } = useTimeState();

  return (
    <div className="sf-timeline">
      <button className="sf-btn sf-btn--primary" onClick={() => timeController.toggle()}>
        {playing ? "⏸" : "▶"}
      </button>
      <div className="sf-timeline__speeds">
        {SPEEDS.map((s) => (
          <button
            key={s}
            className={`sf-btn sf-btn--ghost ${speed === s ? "is-active" : ""}`}
            onClick={() => timeController.setSpeed(s)}
          >
            {s}×
          </button>
        ))}
      </div>
      <input
        className="sf-timeline__scrub"
        type="range"
        min={tMin}
        max={tMax}
        value={cursor}
        step={100}
        onChange={(e) => timeController.seek(Number(e.target.value))}
      />
      <span className="sf-timeline__clock">{fmtClock(cursor)}</span>
    </div>
  );
}
