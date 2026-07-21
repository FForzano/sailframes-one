import { useEffect, useRef, type MutableRefObject } from "react";
import { useNavigate } from "react-router-dom";

const COMMIT_THRESHOLD_PX = 60;
// Below this drag distance, direction hasn't been decided yet — lets a
// vertical scroll start normally instead of being hijacked immediately.
const DIRECTION_LOCK_PX = 10;
// Finger moves further than this without the content visually catching up
// as fast — a soft "rubber band" rather than a 1:1 follow past the edge.
const RESISTANCE = 0.5;
const SLIDE_MS = 180;

// Elements that own their own horizontal touch gestures (map panning, chart
// interaction, scrollable tables/tabs, form controls, modals) — a swipe
// starting on one of these must not also page-navigate the whole app.
const BAIL_SELECTOR =
  ".leaflet-container, .recharts-wrapper, .sf-tablewrap, .sf-tabs, .sf-modal__backdrop, input, textarea, select";

/** Instagram-style drag-to-switch-tab. Attach the returned ref to the
 * element wrapping the routed content (see AppShell's `<main>`): it's
 * translated live under the finger while dragging, then either slides the
 * rest of the way out (committing to the next/previous section in `paths`,
 * ordered to match the action bar) or snaps back if the drag didn't clear
 * the threshold.
 *
 * All touch listeners here are PASSIVE — the horizontal drag is separated
 * from native vertical scroll entirely by `touch-action: pan-y` on `.sf-main`
 * (global.css), NOT by preventDefault. That's deliberate: a non-passive
 * touchmove listener anywhere in the touch path forces iOS/WKWebView to hold
 * every scroll gesture on the main thread (slow path) for its whole
 * duration, and removing the listener mid-gesture doesn't restore the fast
 * path for the in-flight gesture — which is what made vertical scrolling
 * stutter. With pan-y the browser decides the axis at gesture start: a
 * horizontal-first gesture isn't a vertical pan, so the browser does no
 * native scrolling and leaves the X translation to us; a vertical-first
 * gesture scrolls natively (buttery, on the compositor) and we simply never
 * lock horizontal. */
export function useSwipeNavigation<T extends HTMLElement>(
  paths: string[],
  currentPath: string,
): MutableRefObject<T | null> {
  const navigate = useNavigate();
  const ref = useRef<T | null>(null);
  // Re-read on every touchend via refs (not state) so the listeners set up
  // once in the effect below always see the latest route/path list.
  const pathsRef = useRef(paths);
  pathsRef.current = paths;
  const currentPathRef = useRef(currentPath);
  currentPathRef.current = currentPath;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    let origin: { x: number; y: number } | null = null;
    let locked: "h" | "v" | null = null;

    const setTransform = (dx: number, easing: "out" | "in" | false) => {
      el.style.transition = easing ? `transform ${SLIDE_MS}ms ease-${easing}` : "none";
      el.style.transform = dx === 0 ? "" : `translateX(${dx}px)`;
    };

    const onTouchStart = (e: TouchEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest(BAIL_SELECTOR)) {
        origin = null;
        return;
      }
      locked = null;
      origin = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    };

    const onTouchMove = (e: TouchEvent) => {
      if (!origin) return;
      const dx = e.touches[0].clientX - origin.x;
      const dy = e.touches[0].clientY - origin.y;
      if (!locked) {
        if (Math.abs(dx) < DIRECTION_LOCK_PX && Math.abs(dy) < DIRECTION_LOCK_PX) return;
        locked = Math.abs(dx) > Math.abs(dy) ? "h" : "v";
      }
      // Only a horizontal drag translates the page; a vertical one is left to
      // scroll natively (passive — no preventDefault, see the hook comment).
      if (locked !== "h") return;
      setTransform(dx * RESISTANCE, false);
    };

    const finish = (dx: number) => {
      const paths = pathsRef.current;
      const currentIndex = paths.findIndex((p) => currentPathRef.current.startsWith(p));
      const nextIndex = dx < 0 ? currentIndex + 1 : currentIndex - 1;
      const commit =
        locked === "h" &&
        Math.abs(dx) >= COMMIT_THRESHOLD_PX &&
        currentIndex !== -1 &&
        nextIndex >= 0 &&
        nextIndex < paths.length;

      if (!commit) {
        setTransform(0, "out");
        return;
      }
      const width = el.getBoundingClientRect().width;
      setTransform(dx < 0 ? -width : width, "in");
      window.setTimeout(() => {
        navigate(paths[nextIndex]);
        // New content mounts in the same wrapper — start it just off-screen
        // on the entry side, with no transition...
        setTransform(dx < 0 ? width : -width, false);
        // ...then slide it in once that off-screen position has actually
        // been painted. A single rAF isn't reliable enough on every WebView
        // to guarantee a paint happened before the next style change — the
        // two can get coalesced into one frame, which skips straight to the
        // slide-in from wherever the transform happened to be a moment ago
        // and reads as a stray bounce. The second rAF (running in the frame
        // *after* the first was called, i.e. after that paint) removes the
        // race.
        requestAnimationFrame(() => requestAnimationFrame(() => setTransform(0, "out")));
      }, SLIDE_MS);
    };

    const onTouchEnd = (e: TouchEvent) => {
      if (!origin) return;
      const dx = e.changedTouches[0].clientX - origin.x;
      origin = null;
      finish(dx);
    };

    const onTouchCancel = () => {
      origin = null;
      setTransform(0, "out");
    };

    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("touchend", onTouchEnd, { passive: true });
    el.addEventListener("touchcancel", onTouchCancel, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
      el.removeEventListener("touchcancel", onTouchCancel);
    };
  }, [navigate]);

  return ref;
}
