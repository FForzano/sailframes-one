import type { CapabilityHelpers } from "@/hooks/useCapabilities";

// Nav entries are typed data (replaces the reference app's sidebarLinks.json).
// `visible` filters an entry by capabilities; when absent the entry always
// shows. Glyphs are placeholders — swap for a real icon set in a later milestone.
export interface NavEntry {
  to: string;
  labelKey: string; // i18n key
  glyph: string;
  visible?: (h: CapabilityHelpers) => boolean;
}

// Public top-nav (Navbar) — always available, auth or not.
export const publicNav: NavEntry[] = [
  { to: "/", labelKey: "nav.home", glyph: "🏠" },
  { to: "/races", labelKey: "nav.races", glyph: "🏁" },
  { to: "/sessions", labelKey: "nav.sessions", glyph: "🌊" },
  { to: "/fleet", labelKey: "nav.fleet", glyph: "📡" },
];

// Personal-area nav (Sidebar on desktop, bottom ActionBar on mobile). A SINGLE
// area for every role — entries appear/disappear by capability, not by a
// separate per-role dashboard.
export const appNav: NavEntry[] = [
  { to: "/app", labelKey: "nav.dashboard", glyph: "🧭" },
  { to: "/app/sessions", labelKey: "nav.mySessions", glyph: "🌊" },
  { to: "/app/boats", labelKey: "nav.boats", glyph: "⛵" },
  { to: "/app/clubs", labelKey: "nav.clubs", glyph: "🏛️" },
  { to: "/app/groups", labelKey: "nav.groups", glyph: "👥" },
  {
    to: "/app/devices",
    labelKey: "nav.devices",
    glyph: "🛰️",
    visible: (h) => h.canManageAnyBoat || h.canManageAnyClub,
  },
  {
    to: "/app/events",
    labelKey: "nav.events",
    glyph: "📅",
    visible: (h) =>
      h.isSuperadmin ||
      h.can("regatta.manage") ||
      h.can("raceday.manage") ||
      h.can("race.create"),
  },
  {
    to: "/app/admin",
    labelKey: "nav.admin",
    glyph: "🛠️",
    visible: (h) => h.isSuperadmin || h.can("admin") || h.can("user.manage"),
  },
  { to: "/app/profile", labelKey: "nav.profile", glyph: "👤" },
];

export function visibleEntries(entries: NavEntry[], h: CapabilityHelpers): NavEntry[] {
  return entries.filter((e) => e.visible?.(h) ?? true);
}
