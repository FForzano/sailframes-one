import { useEffect, useState } from "react";

export type Breakpoint = "mobile" | "tablet" | "desktop";

// Drives the responsive nav: ActionBar (bottom tabs) on mobile/tablet, Sidebar
// on desktop. Breakpoints match the reference app (lg = 1024, sm = 640).
export function breakpointOf(width: number): Breakpoint {
  if (width >= 1024) return "desktop";
  if (width >= 640) return "tablet";
  return "mobile";
}

export function useScreenWidth() {
  const [width, setWidth] = useState(() =>
    typeof window === "undefined" ? 1280 : window.innerWidth,
  );

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const breakpoint = breakpointOf(width);
  return {
    width,
    breakpoint,
    isMobile: breakpoint === "mobile",
    isTablet: breakpoint === "tablet",
    isDesktop: breakpoint === "desktop",
    /** true on mobile+tablet — where the bottom ActionBar shows */
    isCompact: breakpoint !== "desktop",
  };
}
