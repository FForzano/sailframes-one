import { useEffect, useRef } from "react";

/** Attach the returned ref to a sentinel element at the end of a list —
 * `onIntersect` fires once whenever it scrolls into view (guarded by
 * `enabled` so it stops firing once there's no next page/already loading). */
export function useInfiniteScrollSentinel<T extends HTMLElement>(
  onIntersect: () => void,
  enabled: boolean,
) {
  const ref = useRef<T | null>(null);
  const onIntersectRef = useRef(onIntersect);
  onIntersectRef.current = onIntersect;

  useEffect(() => {
    const el = ref.current;
    if (!el || !enabled) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) onIntersectRef.current();
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [enabled]);

  return ref;
}
