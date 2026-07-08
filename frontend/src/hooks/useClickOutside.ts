import { useEffect, type RefObject } from "react";

/** Calls `onOutside` on the first `mousedown` outside `ref`'s element — for
 * closing/committing a floating panel (options menu, inline editor) without
 * an explicit close button. Only listens while `active` is true. */
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  active: boolean,
  onOutside: () => void,
) {
  useEffect(() => {
    if (!active) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOutside();
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [active, ref, onOutside]);
}
