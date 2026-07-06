import { useSyncExternalStore } from "react";

// Playback clock shared by map / chart / timeline (port of the legacy
// time-sync.js EventTarget). Keeps only cursor + play state in React-visible
// state; the heavy sensor arrays stay in component refs. Advancing uses real
// wall-clock elapsed × speed so playback is frame-rate independent.
export interface TimeState {
  tMin: number; // ms
  tMax: number; // ms
  cursor: number; // ms
  playing: boolean;
  speed: number; // 1 / 2 / 4 …
}

class TimeController {
  private state: TimeState = { tMin: 0, tMax: 0, cursor: 0, playing: false, speed: 1 };
  private listeners = new Set<() => void>();
  private raf = 0;
  private lastTick = 0;

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  getSnapshot = () => this.state;

  private emit() {
    // New object identity so useSyncExternalStore re-renders.
    this.state = { ...this.state };
    this.listeners.forEach((l) => l());
  }

  setBounds(tMin: number, tMax: number) {
    this.state.tMin = tMin;
    this.state.tMax = tMax;
    this.state.cursor = tMin;
    this.emit();
  }

  seek(cursor: number) {
    this.state.cursor = Math.max(this.state.tMin, Math.min(this.state.tMax, cursor));
    this.emit();
  }

  setSpeed(speed: number) {
    this.state.speed = speed;
    this.emit();
  }

  play() {
    if (this.state.playing || this.state.tMax <= this.state.tMin) return;
    if (this.state.cursor >= this.state.tMax) this.state.cursor = this.state.tMin;
    this.state.playing = true;
    this.lastTick = performance.now();
    this.emit();
    this.loop();
  }

  pause() {
    this.state.playing = false;
    cancelAnimationFrame(this.raf);
    this.emit();
  }

  toggle() {
    this.state.playing ? this.pause() : this.play();
  }

  private loop = () => {
    if (!this.state.playing) return;
    const now = performance.now();
    const dt = now - this.lastTick;
    this.lastTick = now;
    let next = this.state.cursor + dt * this.state.speed;
    if (next >= this.state.tMax) {
      next = this.state.tMax;
      this.state.cursor = next;
      this.pause();
      return;
    }
    this.state.cursor = next;
    this.emit();
    this.raf = requestAnimationFrame(this.loop);
  };
}

// One controller per app; a race view resets its bounds on load.
export const timeController = new TimeController();

export function useTimeState(): TimeState {
  return useSyncExternalStore(timeController.subscribe, timeController.getSnapshot);
}
