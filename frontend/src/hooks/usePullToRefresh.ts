import { useEffect, useRef, useState } from "react";
import { Capacitor } from "@capacitor/core";

export const PULL_TRIGGER_PX = 70;
const MAX_PULL_PX = 100;
const RESISTANCE = 0.5;
const DIRECTION_LOCK_PX = 10;

// Same rationale as useSwipeNavigation's BAIL_SELECTOR: elements that own
// their own touch gestures must not also start a pull-to-refresh drag.
const BAIL_SELECTOR =
  ".leaflet-container, .recharts-wrapper, .sf-tablewrap, .sf-tabs, .sf-modal__backdrop, input, textarea, select";

// document.scrollingElement.scrollTop is the authoritative "how far from
// the top" value — window.scrollY can lag or read stale during a native
// WebView's own rubber-band bounce, which would otherwise let a drag
// anywhere near the top (not just genuinely at it) start a pull.
const scrollTop = () => document.scrollingElement?.scrollTop ?? 0;

/** Social-app-style drag-down-to-refresh, native platforms only (pull-to-
 * refresh on the web would fight the browser's own overscroll behavior).
 * Only engages when the drag starts at the very top of the page's scroll;
 * past PULL_TRIGGER_PX on release it calls `onRefresh` and reports
 * `refreshing` while it's in flight, so the caller can render a spinner. */
export function usePullToRefresh(onRefresh: () => Promise<unknown>) {
  const [pull, setPull] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    let origin: { x: number; y: number } | null = null;
    let locked: "pull" | "other" | null = null;
    let distance = 0;
    let busy = false;

    // touchmove/touchend/touchcancel are only attached for the duration of a
    // gesture that starts at the very top of the page (see onTouchStart) and
    // removed as soon as it ends or turns out not to be a pull. A
    // non-passive touchmove listener registered permanently on `window`
    // forces WKWebView to wait on the JS main thread before starting native
    // scroll on EVERY touch anywhere on the page — not just ones near the
    // top — which is what made scrolling (especially back up from the
    // bottom) feel like it randomly stalled. Scoping the listener to just
    // the gesture that can actually become a pull keeps the rest of the
    // page's scrolling on the browser's normal fast path.
    const detachMove = () => {
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", finish);
      window.removeEventListener("touchcancel", finish);
    };

    const onTouchStart = (e: TouchEvent) => {
      if (busy) return;
      const target = e.target as HTMLElement;
      if (target.closest(BAIL_SELECTOR) || scrollTop() > 0) {
        origin = null;
        return;
      }
      locked = null;
      origin = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      window.addEventListener("touchmove", onTouchMove, { passive: false });
      window.addEventListener("touchend", finish, { passive: true });
      window.addEventListener("touchcancel", finish, { passive: true });
    };

    const onTouchMove = (e: TouchEvent) => {
      if (!origin) return;
      const dx = e.touches[0].clientX - origin.x;
      const dy = e.touches[0].clientY - origin.y;
      if (!locked) {
        if (Math.abs(dx) < DIRECTION_LOCK_PX && Math.abs(dy) < DIRECTION_LOCK_PX) return;
        locked = dy > 0 && dy > Math.abs(dx) ? "pull" : "other";
        // Direction resolved as not-a-pull: stop intercepting this gesture's
        // remaining touchmove events so it falls back to native scrolling.
        if (locked !== "pull") detachMove();
      }
      if (locked !== "pull" || scrollTop() > 0) return;
      e.preventDefault();
      distance = Math.min(dy * RESISTANCE, MAX_PULL_PX);
      setPull(distance);
    };

    const finish = () => {
      const wasPulling = locked === "pull";
      origin = null;
      locked = null;
      detachMove();
      if (!wasPulling) return;
      if (distance >= PULL_TRIGGER_PX) {
        busy = true;
        setPull(PULL_TRIGGER_PX);
        setRefreshing(true);
        onRefreshRef.current().finally(() => {
          busy = false;
          setRefreshing(false);
          setPull(0);
        });
      } else {
        setPull(0);
      }
      distance = 0;
    };

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      detachMove();
    };
  }, []);

  return { pull, refreshing };
}
